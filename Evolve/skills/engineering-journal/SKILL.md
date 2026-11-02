---
name: engineering-journal
description: Keep a project's knowledge truthful and resumable. Docs split by purpose (SPEC = what it is, design = why plus rejected alternatives, LOG = append-only lessons journal plus status history, README = current status/next as falsifiable claims, RUNBOOK = procedures, ONBOARDING, topic docs, resumable plan docs, user guides), commit-per-milestone with journal and status in the same commit, journal entries headed by the lesson with measured numbers, wrong turns and the test that pins the fix, event-driven design review gates, "what the build changed about the spec", numbers that carry their date and dataset, and the rule that facts-that-run become tests while prose records why. Use when starting a project's documentation, writing a journal/changelog entry, recording a design decision, updating status after a milestone, planning a slice of work, or when docs keep drifting from the code.
---

# Engineering journal: knowledge that stays true

> Prose does not run, so nothing fails when it goes stale. Put *what the code does* in code
> and tests; put *why*, *what was tried and rejected*, and *what we learned* in prose —
> those stay true.

## 1. One purpose per document

| Doc | Purpose | Audience | Changes when |
|---|---|---|---|
| `SPEC.md` | What the system **is** when done: architecture in a few lines, the contract rules, "done" | everyone | almost never ("the validator IS the spec — prose drifts, code doesn't") |
| `design.md` | **Why**: decisions, alternatives rejected (with reasons), sequencing, open questions, review gates | builders | an interface is about to freeze, or a new axis of variation appears |
| `LOG.md` | **Append-only** journal of lessons + a one-line-per-milestone status history | the next agent/engineer | every milestone |
| `README.md` | **Current status + Next**, capability/tenant matrix, how to run/test/review/deploy | everyone | every milestone, same commit |
| `RUNBOOK.md` | Procedures: deploy, backup, recover, routine ops | the operator at 3am | ops change — and it **ships** with the product |
| `ONBOARDING.md` | Adding a tenant/component, with **two** definitions of done (data vs production) | builders | the scaffold changes |
| `docs/<concept>.md` | Durable reasoning about one hard concept (authority, identity vs presence, …) | builders + reviewers | rarely |
| `docs/<plan>.md` | Resumable working plan: status, checkboxes, decisions, **Resume here** | the next session | every working session |
| user guide | Journeys for the people who run it; what a refusal means; what it won't do | end users | features ship |
| `CLAUDE.md` / `AGENTS.md` | Rules for coding agents (see `agentic-workbench`) | coding agents | a rule is learned |

A docs-map table at the top of the README routes readers. Each doc's header states its
purpose and points at its siblings, so nobody writes status into SPEC or rationale into README.

## 2. The journal (LOG)

**Entry heading = the lesson, not the activity.**
`### 2026-03-04 — a cache keyed on a hand-written input list served yesterday's answer`
beats `### 2026-03-04 — cache fixes`.

**Entry body** (keep the skeleton even when short):
1. **Trigger** — a user report (quote it), a review finding, a measurement.
2. **Mechanism** — what actually happened, measured: numbers, tables, which dataset/date.
3. **Fix** — exact files, functions, tests.
4. **The transferable rule** — one bold sentence someone in another codebase could use.
5. **Not done / still open / deliberately not changed** — with reasons.
6. **Tests** — names, and "fails at `<sha>` with `<assertion>`".
7. **Gate** — "N fast + M acceptance files".

Write in first person, including the wrong turns ("I explained it wrong twice") — the
journal is how the next agent avoids repeating a diagnosis. **Corrections are visible**:
"CORRECTION to the 2026-03-02 entry: …" or an inline "An earlier draft of this entry said…";
never silently rewrite history.

**Status history line** (one per milestone):
`- **2026-03-10 (release line)** — deploys now ship an artifact built from main with a provenance record; 3 tests, fail at base; gate 88 fast + 9 acceptance; not deployed. Next: read the record back.`

**Ordering and merges** — pick ONE convention and test it (the source system drifted:
an "append-only" file that prepended, plus a tail appended after the oldest entry). Options:
- one file per entry (`journal/YYYY-MM-DD-slug.md`) plus a generated index — no merge conflicts;
- a single `LOG.md` with `LOG.md merge=union` in `.gitattributes` so parallel branches'
  appended entries both survive a merge.

## 3. README status: falsifiable, bounded

- Each status item: **bold headline claim** → numbers and scope ("37 records change on the
  nightly sync — 12 …, 25 …") → **Next:** what has to happen for it to be done (often
  "deploy and confirm on the floor that …").
- Bound it: keep the newest N items; older ones live in the LOG status history. (A README
  "Current status" that grows past ~1,000 lines stops being read.)
- Keep explicit, honest gap lists: "Still uncovered: these paths have no automated guard"
  with the tracking issue.

## 4. Commit per milestone, docs in the same commit

A coherent milestone updates `LOG.md` (entry + status line) and README Status/Next **in the
same commit as the code**. The reviewer treats a substantive PR without them as MUST-FIX,
and a contentless entry ("updated the thing") as a finding.

## 5. Decision records (design.md sections)

```
## N. <Decision> (YYYY-MM-DD)
### The problem            — what hurts, measured
### The decision           — the rule, in one paragraph
### Alternatives considered and rejected — table: option | why rejected
### Deliberately not changed — and why (scope discipline)
### Open questions
### Impact on tests        — which proofs changed, which divergences are accepted and why
```
Also record **what was considered and rejected** in topic docs — it is the part no code can
hold and the part that stops the next person re-proposing it.

**Review gates are event-driven, not calendar-driven**: review when an interface is about to
freeze or a new axis of variation appears; skip routine ports. Log each verdict and its
must-fix list.

## 6. Plans for slices of work

- **Delivery decision** + **v1 simplicity rules** as an explicit "No X" list (no database,
  no new frontend framework, no generic table editor, no arbitrary-row write endpoint, no
  reimplementing server logic in the browser …). "Simplicity means removing irrelevant
  generalization, not weakening integrity."
- **Pick the first write pilot by semantic simplicity** (the tenant or module where the data has
  the fewest ambiguities), and list what that choice lets you defer.
- Slices with **scope gate**, **exit criteria** (some must be about real users: "an expert
  resolves one blocker before it reaches today"), tests owed.
- "Everything after the committed slices is selected from pilot evidence" — don't build
  because it appears in the long-term idea.
- After building: **"What shipped, and what the build changed about this spec"** — the
  corrections reality forced.
- **Baseline snapshot as scoped claims** ("410 planned rows to <date>; 63 of them …")
  that regression fixtures can reproduce.
- A **Resume here** section updated at the end of every session.

## 7. Numbers are claims

- Every number carries **date, dataset, conditions** (idle vs under load, cold vs warm).
- Never re-quote a figure you didn't re-derive; when you correct one, grep for it everywhere
  (corrected numbers survive in the files nobody edited).
- Audits are **scripts**, not one-off notebooks, so the number can be re-derived.
- Never present two scopes as one number; detector/report definitions state their scope.
- "A plausible number is the most dangerous kind" — cross-check with an independent path.

## 8. Incident notes and user guides

Incident note: **Problem** (as the user saw it) → **Root cause** → **What we fixed** →
**If it happens again** (what to check, who to call). User guide: what the tool is for,
"before you touch anything", journeys in the order of a real day, what a refused save
means, what the tool deliberately will not do, a few habits.

## Translation
Works unchanged in any stack. In a portfolio/product repo: `docs/adr/NNNN-title.md` for
decision records, `journal/` fragments + a generated `CHANGELOG.md`, and a GitHub PR
template that asks for the journal entry and the status line.

## Checklist (per milestone)
- [ ] LOG entry headed by the lesson, with numbers, fix, tests (fails at base), still-open.
- [ ] Status-history line; README Status/Next updated — same commit.
- [ ] Decision recorded with rejected alternatives if an interface changed.
- [ ] Old numbers/names grepped and corrected everywhere.

Templates: [references/templates.md](references/templates.md).

## Related skills
`agentic-workbench` (prose-drift checks, PR claims) · `test-gates` · `architecture-bootstrap`
