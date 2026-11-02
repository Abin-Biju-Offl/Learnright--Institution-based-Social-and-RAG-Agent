---
name: readiness-detectors
description: Build a readiness or data-quality board people actually act on. Covers an issue model where an issue is a root cause that fans out to the runs it affects, one pure severity function (urgency × blocking × confidence) shared by every detector, keeping questions with different inputs apart (a stale feed never suppresses checks that never read it; unknown is never rendered as blocked), exact predicates with stated scope, grouping by the expert's unit of work and by action rather than category, every issue carrying exactly one of an in-app form, a deep link or a named external owner, snooze with reason and expiry (recommended), as_of plus source revision on every number, detectors that never flag human-chosen differences, freshness and calibration signals, and tests per detector. Use when building data-quality checks, readiness or health dashboards, validation queues, alerting rules, or any "what is wrong and what do I do about it" screen.
---

# Readiness detectors: a queue people act on, not wallpaper

> A severity scale whose top bucket is the common case has no top bucket.
> A detector with no action is a bug.

The first cut of the reference board had well over a hundred issues, almost all "critical",
entity-shaped, with literal severities — correct and useless. The design below is what made
it actionable (sections marked *recommended* were designed but not built there).

## 1. Keep questions with different inputs apart

- **A stale feed must never suppress checks that never read it.** "Can this planned run be
  executed at all?" reads plans, templates and approvals; it must resolve for a future date with
  no presence data at all.
- **Don't attach a dated-feed concern to a plan-time question.** The first design gave every
  planned run a second "ready today, with the people here?" state and asked users to fetch
  presence data for planned dates — a category error (presence lands when a shift ends, not
  when a plan is written). It was removed. What survived: findings about presence are **dated by
  their own evidence** (the latest landed capture), not by a planned run.
- `unknown` renders distinctly from `blocked` — missing evidence is not a red line.

## 2. An issue is a root cause

```json
{
  "id": "missing-template:KIT-17",
  "detector": "missing-template",
  "title": "Planned item has no template",
  "subject": "KIT-17",
  "blocking": "production_blocking",
  "confidence": "confirmed",
  "affected_runs": [{"date": "2026-04-09", "unit": "4", "role": "planned"}],
  "affected_run_count": 3,
  "earliest_due_date": "2026-04-08",
  "severity": "critical",
  "severity_score": 9.0,
  "evidence": "no template and no observed version for KIT-17",
  "action": {"kind": "upload-template", "deep_link": "#plan?date=2026-04-08&item=KIT-17"},
  "owner": "planner",
  "as_of": "2026-04-06T05:30:00Z",
  "source_revision": "a91c…"
}
```
- **One cause → one issue → N affected runs** (never one issue per run).
- `affected_runs` may be empty (freshness, identity, unresolved-source issues); then
  `earliest_due_date` is `null` — not severity zero. Carry `affected_run_count` separately.
- A run is `blocked` iff at least one `production_blocking` issue names it.
- Group by the **expert's unit of work**: certification gaps grouped *per task* (with the
  people listed and the form prefilled) turned hundreds of per-person rows into a few dozen
  decisions.

## 3. One severity function

```
score      = urgency × blocking × confidence          (an EXAMPLE scale — tune for your domain)
urgency    today 5 · +1d 4 · +2–3d 3 · +4–7d 2 · later/undated 1   (from earliest_due_date)
blocking   production_blocking 3 · degrading 1.5 · advisory 0.5
confidence confirmed 1.0 · inferred 0.75 · unreviewed_source 0.5
bucket     critical ≥ 9 · high ≥ 4.5 · medium ≥ 1.5 · low < 1.5
ties       → higher affected_run_count first (fix what unblocks most runs)
```
- A pure function shared by every detector; **no detector hardcodes a severity literal**.
- The shape matters more than the numbers: urgency from the *earliest* affected date, a
  blocking class, and a confidence that demotes unreviewed evidence.
- **"Blocking" means only blocking.** Something is happening even if the system can't
  predict it well (a seated but unrated person) → `degrading`. Marking those blocking turned
  every run red and made the board useless for triage.
- `confidence` demotes issues derived from evidence the system itself could not resolve,
  so unreviewed source rows never outrank confirmed blockers.

## 4. Detectors

- **Exact predicates with stated scope** ("rows whose role is `planned` in the next 4 days").
  Two differently-scoped numbers differ permanently — never present them as one number.
- **Report every instance**, not `min()` — with several zero-capacity items, "the bottleneck"
  is an arbitrary tie-break.
- **Never report a difference a human chose** (see `human-decision-authority`): read the
  authoritative layer, compare by identity not position, collapse to latest-per-entity first.
- **Join to evidence**: a list of unknown badge cards proves nothing until joined to actual
  scans for the date.
- **Sweep the outer population**: detectors that start from what the system holds cannot see
  what it doesn't (a large share of active people were invisible to every detector because none
  started from the HR master).
- Freshness / source-health issues (feed last landed N days ago, unresolved queues) are
  `degrading`, with no dated impact.
- **Predicted-vs-actual divergence is a calibration signal**: `advisory`, labelled
  "calibration", never evidence that the inputs are wrong (downtime, changeovers and
  supply all move actuals).
- Detectors are read-only and **never accept a table name, path or predicate from the client**.

## 5. Route by action

- Group the board by **action** ("upload template", "approve assignment", "certify",
  "map item", "refresh feed", "fix in source system"); category is a filter.
- **Every issue carries exactly one of: an in-app form, a deep link, or a named external
  owner with evidence.** An issue with none is a spec bug. Check the named fix exists as a
  control (a "re-promote" button that didn't exist shipped twice).
- Order actions by **consequence, not volume** (four missing templates outrank thirty
  source reviews).
- One contextual fix panel under the action chips that switches shape by action kind,
  prefilled from the issue; batch fixes apply in **one transaction** (one lock, one revision
  check, one backup, one audit record) through **one validator** shared with the single-item path.

## 6. Snooze — or the board becomes wallpaper (*recommended*)

Designed in the reference system but deferred while the first board was cut down to
actionable detectors; the need it answers (a queue that keeps growing) was real.

Sidecar rows: `issue_id, reason, actor, snoozed_at, expires_on` (max ~14 days). A snoozed issue
is hidden from the default view, counted in a "snoozed" chip, and **reappears on expiry or when
its affected runs change**.

## 7. Provenance on every number

Every response and every rendered metric carries `as_of` (UTC) and the `revision` of its
sources. Cache the board keyed on the source revision (see `console-backend`), and make sure
the revision does not move when nothing meaningful changed.

## 8. Ship small; record what the build changed

Ship first the detectors whose fix the user performs **in this app**; list the deferred ones.
Afterwards, write "what shipped, and what the build changed about this spec" — the
corrections reality forced (collapsed predicates, regrouping, re-graded blocking).

## Tests
- `severity_score` as a pure, table-driven test (including undated issues).
- Each detector against a fixture: one positive, one negative, one boundary.
- Fan-out: one missing template → one issue with N affected runs, not N issues.
- Plan readiness resolves for a future date that has no presence data at all.
- Every emitted issue has a form, a link or an owner.
- Snooze hides, expires, and reappears on change.
- A human-authored difference produces no issue.

## Translation: FastAPI · Postgres · React

| Concept | Your stack |
|---|---|
| Board endpoint | `GET /readiness?from=<date>&days=4` → `{issues, runs, as_of, revision}`; `POST /readiness/snooze` |
| Detector | one SQL view or Python function per detector, registered with `{id, scope, blocking, confidence, action}` |
| Severity | a pure Python function + unit tests; never in SQL literals |
| Cache | key on the source revision (max `updated_at`/build id of the inputs) |
| UI | React: action chips → filtered list → one fix panel; TanStack Query keyed on `revision` |

Templates: [references/templates.md](references/templates.md).

## Related skills
`human-decision-authority` · `decision-ledger` · `console-backend` · `test-gates`
