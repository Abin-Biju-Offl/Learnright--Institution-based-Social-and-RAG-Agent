# readiness-detectors — templates

## §1 Issue model + severity

```python
from dataclasses import dataclass, field
from datetime import date

URGENCY = [(0, 5.0), (1, 4.0), (3, 3.0), (7, 2.0)]          # days out (≤) → weight (example scale)
BLOCKING = {"production_blocking": 3.0, "degrading": 1.5, "advisory": 0.5}
CONFIDENCE = {"confirmed": 1.0, "inferred": 0.75, "unreviewed_source": 0.5}
BUCKETS = [(9.0, "critical"), (4.5, "high"), (1.5, "medium"), (0.0, "low")]


@dataclass
class Issue:
    id: str
    detector: str
    title: str
    subject: str
    blocking: str
    confidence: str
    evidence: str
    action: dict | None = None          # {"kind": ..., "form": ...} or {"deep_link": ...}
    owner: str | None = None            # named external owner when there is no in-app fix
    affected_runs: list[dict] = field(default_factory=list)

    @property
    def earliest_due_date(self) -> str | None:
        return min((r["date"] for r in self.affected_runs), default=None)


def severity_score(issue: Issue, as_of: date) -> float:
    due = issue.earliest_due_date
    if due is None:
        urgency = 1.0
    else:
        days_out = (date.fromisoformat(due) - as_of).days
        urgency = next((w for limit, w in URGENCY if days_out <= limit), 1.0)
    return urgency * BLOCKING[issue.blocking] * CONFIDENCE[issue.confidence]


def bucket(score: float) -> str:
    return next(name for floor, name in BUCKETS if score >= floor)


def sort_board(issues: list[Issue], as_of: date) -> list[Issue]:
    return sorted(issues, key=lambda i: (-severity_score(i, as_of), -len(i.affected_runs), i.id))
```

## §2 Detector registry

```python
from typing import Callable, Iterable

DETECTORS: dict[str, dict] = {}


def detector(id: str, *, scope: str, blocking: str, confidence: str, action: str | None,
             owner: str | None = None):
    """Register a detector with its metadata. Exactly one of action/owner must be set."""
    if (action is None) == (owner is None):
        raise ValueError(f"{id}: an issue needs exactly one of an in-app action or a named owner")

    def wrap(fn: Callable[..., Iterable[Issue]]):
        DETECTORS[id] = {"fn": fn, "scope": scope, "blocking": blocking,
                         "confidence": confidence, "action": action, "owner": owner}
        return fn
    return wrap


@detector("missing-template", scope="planned + changeover rows, next 4 days",
          blocking="production_blocking", confidence="confirmed", action="upload-template")
def missing_template(ctx) -> Iterable[Issue]:
    by_item: dict[str, list[dict]] = {}
    for run in ctx.planned_runs():
        if run["item"] not in ctx.templates and (run["unit"], run["item"]) not in ctx.observed:
            by_item.setdefault(run["item"], []).append(run)            # fan-out: one issue per CAUSE
    for item, runs in sorted(by_item.items()):
        yield Issue(id=f"missing-template:{item}", detector="missing-template",
                    title="Planned item has no template", subject=item,
                    blocking="production_blocking", confidence="confirmed",
                    evidence=f"no template and no observed version for {item}",
                    action={"kind": "upload-template", "deep_link": f"#plan?item={item}"},
                    affected_runs=runs)
```

## §3 Snooze

```python
def visible(issues: list[Issue], snoozes: dict[str, dict], today: date) -> tuple[list[Issue], int]:
    shown, hidden = [], 0
    for issue in issues:
        s = snoozes.get(issue.id)           # latest snooze row per issue
        still_snoozed = (s is not None
                         and date.fromisoformat(s["expires_on"]) >= today
                         and s["affected_fingerprint"] == fingerprint(issue.affected_runs))
        if still_snoozed:
            hidden += 1                     # counted in the "snoozed" chip
        else:
            shown.append(issue)             # expired, or its affected runs changed → back
    return shown, hidden
```

## §4 Response envelope

```python
def board(ctx, start: date, days: int) -> dict:
    issues = [i for d in DETECTORS.values() for i in d["fn"](ctx)]
    shown, snoozed = visible(issues, ctx.snoozes(), start)
    return {
        "as_of": ctx.now_utc_iso(),
        "revision": ctx.source_revision(),     # the inputs' version; cache key
        "issues": [serialize(i, start) for i in sort_board(shown, start)],
        "snoozed_count": snoozed,
        "runs": run_states(ctx, issues),        # per planned run: ready | blocked (unknown when evidence is missing)
    }
```

## §5 Tests

```python
check(severity_score(issue(due=None, blocking="advisory", confidence="confirmed"), D0) == 0.5,
      "undated advisory issue scores 1 × 0.5 × 1")
issues = list(missing_template(ctx_with(planned=[("6", "X", D1), ("7", "X", D2)], templates=set())))
check(len(issues) == 1 and len(issues[0].affected_runs) == 2, "one cause → one issue, two runs")
issues = list(missing_template(ctx_with(planned=[("6", "X", D1)], templates=set(), observed={("6", "X")})))
check(issues == [], "an observed version counts: no issue for a unit someone walked")
for d in DETECTORS.values():
    for i in d["fn"](rich_fixture_ctx()):
        check(bool(i.action) != bool(i.owner), f"{i.id} has exactly one of action/owner")
```
