# human-decision-authority — templates

## §1 `docs/decision-authority.md` skeleton (write one per domain)

```markdown
# Who decides <what>

> Read before writing any detector or any code that compares two descriptions of <thing>.

## The rule
The <role> is the authority on <thing>. <Template> is a starting point, not a judge.

## The flow, in order
<template> → <authored/observed> → <approved decision> → <schedule> → <execution>
Each layer down is more specific and wins for its question.

## What the system may and may not say
| Situation | Verdict |
|---|---|
| ... | Blocker / Advisory / Not reported / Reported |

## Suggesting a change
Suggestions are not decisions; accepting is authoring; a denial is recorded.

## How this went wrong before (so it is recognisable next time)
- <detector>: <what it compared>, <why that was backwards>, <what fixed it>.

## Practical checks before shipping a detector
1. Could a human have chosen this on purpose? 2. Which source is the authority? 3. Does the
named fix exist as a control? 4. Does the count survive renumbering/re-spelling? 5. Can the
field disagree? 6. Read the rows on real data.
```

## §2 Precedence resolver (most specific human decision wins)

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Version:
    subject: str            # e.g. (unit, design_id)
    group: str              # the authoring crew/team; "" for the template
    effective_from: str     # ISO date; never applies backward
    updated_at: str
    source: str             # "authored" | "observed" | "template"
    payload: dict


SOURCE_RANK = {"template": 0, "observed": 1, "authored": 2}   # same-day tie: the expert's edit wins


def effective_version(versions: list[Version], subject: str, group: str, on: str) -> Version | None:
    mine = [v for v in versions
            if v.subject == subject and v.group == group and v.effective_from <= on]
    if not mine:
        return None          # caller falls back to the template — never to another group's version
    # newest effective date first; on the SAME date the expert's authored edit beats an
    # observation, whatever their timestamps; then the latest timestamp
    return max(mine, key=lambda v: (v.effective_from, SOURCE_RANK[v.source], v.updated_at))
```

## §3 Suggestion lifecycle

```python
# proposals are rows; the latest row per proposal wins (decision-ledger)
# PROPOSED -> ACCEPTED   (accept() calls the SAME save function as a manual edit)
#          -> DENIED     (recorded; hides the suggestion; reason optional but kept)
# DENIED   -> REOPENED   (a new row; the denial row stays)

def accept(proposal_id: str, actor: str) -> None:
    p = load_proposal(proposal_id)
    save_authored_version(p.subject, p.change, actor=actor, reason=f"accepted suggestion {proposal_id}")
    append_decision(proposal_id, "ACCEPTED", actor)


def deny(proposal_id: str, actor: str, reason: str = "") -> None:
    append_decision(proposal_id, "DENIED", actor, reason)
```

## §4 Advisory run record

```
run_outputs/advisory/<date>/<group>/<stamp>/
  problem.json   # exact inputs: pinned items, ratings, rules, targets, seed — enough to re-score
  view.json      # precomputed state at every curve point (the browser only renders these)
  packages.json  # independent change packages: [{id, changes:[...], gain, people_moved}]
  curve.json     # cumulative gain after each package, ordered by gain per change
  report.md      # headline, where-to-stop table, ceiling, what no move can fix, caveats
```

```python
def build_curve(packages, score, start_state):
    """Greedy by value per change, each measured ON TOP of those before. Every step must be a
    gain, so 'stop after N' is safe. (Packages that only pay together must be merged into ONE
    package before this runs — this loop never pairs them itself.)"""
    state, curve, remaining = start_state, [], list(packages)
    while remaining:
        best = max(remaining, key=lambda p: (score(apply(state, p)) - score(state)) / max(1, p.people_moved))
        gain = score(apply(state, best)) - score(state)
        if gain <= 0:
            break
        state = apply(state, best)
        curve.append({"package": best.id, "cumulative": score(state) - score(start_state)})
        remaining.remove(best)
    return curve
```

## §5 What-if endpoint (server scores; client renders)

```python
@router.get("/advisory/{run_id}/evaluate")
def evaluate(run_id: str, skip: list[str] = Query([]), extra: list[str] = Query([])):
    problem = load_problem(run_id)                      # the exact recorded problem
    moves = [m for m in load_packages(run_id) if m.id not in skip] + parse_moves(extra)
    impossible = [m for m in moves if not can_be_true(problem, m)]   # unrated, pinned, immovable
    if impossible:
        raise UserError("cannot be scored: " + "; ".join(m.describe() for m in impossible))  # one error contract
    result = score_with(problem, moves)
    return {"gain": result.gain,
            "warnings": rule_breaks(problem, moves)}   # "crosses a floor", "stops unit 5": allowed, said
```

## §6 Consequence labels instead of hidden options

```json
{
  "candidate": "p-17",
  "available": false,
  "label": "Seated on unit 4 · station 2",
  "cost": "unit 4 drops from 410 to 360/shift",
  "allowed": true
}
```
The UI shows the candidate, the label and the cost; selecting it asks "Move them here" vs
"Cover both" rather than silently swapping.
