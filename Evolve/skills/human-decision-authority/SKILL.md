---
name: human-decision-authority
description: Design how software relates to human decisions so it informs without overruling. Covers authority layering (generic template, then authored or observed version, then approved decision, then schedule, then daily execution; each layer down is more specific and wins), detectors that report contradictions and genuine absences but never a difference a human chose, suggestions vs decisions (accepting is authoring; a denial is recorded), advisory engines and optimizers (nothing applied, packages plus a value curve, a ceiling, "you may" is not "you should"), recommendations that carry their evidence quality, narrow hole-filling over global re-optimization, separate fields for "the problem" and "how it was resolved", and an LLM that runs deterministic tools rather than computing. Use when building recommendations, copilots, optimizers, consistency or anomaly detectors, approval workflows, or any feature that compares a plan against reality or against a template.
---

# Human decision authority: inform, never overrule

> The domain expert is the authority on how their part of the world is set up. A generic
> template is a starting point, not a judge. **A difference from the template is the normal
> case on a real floor, not a defect.**

## 1. The authority stack

```
template            the shared design (e.g. a standard recipe, a reference layout)   STARTING POINT
  ↓
authored / observed the unit's actual build: an expert's edit or what a walk-through saw   AUTHORITATIVE for that unit
  ↓
approved decision   who does what (standing; date-less on purpose)                  A DECISION
  ↓
schedule            what runs when                                                  decides WHEN
  ↓
execution           today's reality (absence-adjusted)                               the day's facts
```
- **Each layer down is more specific and wins** for the question it answers.
- An authored version belongs to the **group that authored it** (where crews rotate, each
  crew's arrangement is its own decision; a group with no version stands on the template,
  never on another group's arrangement).
- Resolve on read, so the most specific human decision is what every consumer sees.
- **Re-applying the template is itself an authored decision.** A "reset this unit to the
  standard template" control records a *new* authored version (copied from the template, dated,
  stamped with who pressed it) that wins by being newest — not a revert, not an exception to the
  stack, and the superseded version stays in history. Detectors read it as authored.

## 2. Detectors: contradictions and absences only

**Report a contradiction (two numbers for one thing) or a genuine absence (nothing to plan
from). Never report a difference a human chose.**

| Situation | Verdict |
|---|---|
| No template AND no observed version | **Blocker** — nothing to plan from |
| No approved decision at all | **Blocker** — nothing to execute |
| Staffed/resourced below the floor that blocks running | **Blocker** |
| Approved decision differs from the authored version | **Advisory** — usually deliberate |
| Unit's build differs from the template where an expert authored or observed it | **Not reported** |
| Something only this unit has | **Not reported** — that is what authoring means |
| A fact about a person/asset is missing (e.g. no rating) | **Reported** — a fact, not a decision |
| Two stores hold different numbers for one item | **Reported** — a contradiction |

The failure shape to recognise: in three days, four detectors shipped "confident,
internally consistent false alarms" — each treated a **more general** source as authoritative
over a **more specific** human decision, then escalated the disagreement (one counted a
renumbering as dozens of differences; one judged people against a frozen copy instead of the
owning table; one blocked units every day for deliberate edits).

**Before shipping any detector** (and see `readiness-detectors`):
1. Could a human have chosen this state on purpose? → advisory at most.
2. Which source is the authority for *this* question? Read that one (the owning table, not a frozen copy).
3. Does the fix the issue names exist as a control the user can press?
4. Would the count survive a renumbering, a re-spelling, a re-export?
5. Can the field it reads ever disagree? (A column copied from the roster cannot contradict the roster.)
6. Run it against real data and **read the rows** before believing it.

## 3. Suggestions are not decisions

- Nothing applies until a human accepts. **Accepting IS authoring**: it goes through the same
  save path as a manual edit and lands as an authored version, which then wins like any other.
- **A denial is a decision**: recorded (append-only, latest row per suggestion wins), lifted
  by a later "reopened" row — never inferred from the suggestion's absence.
- **An accepted thing is not argued with**: the engine never moves or releases a person/item
  a human accepted; accepting the first steps of a chain leaves the rest exactly as offered.
- **Name the evidence**: a recommendation resting on an unrated or defaulted value says
  "re-measure first" — one unsourced value once made many units look like they needed
  restructuring.

## 4. Decision support informs; it does not overrule

- A picker may tell the expert what a choice costs; it may not overrule the choice. Label, don't
  hide: *seated elsewhere* is a label; a blocked action is disabled **with its reason beside it**.
- Refuse a human's own move **only** when it cannot be scored or cannot be true (no rating, a
  pinned item, someone who cannot move). Breaking the engine's soft rules is allowed and the
  consequence is shown beside the number — **"you may" is not "you should"**.
- Human overrides are **additive**: an override adds a placement; it never silently removes
  another decision.
- Report, never resolve, what arithmetic cannot settle (one person approved on two units at
  once: label it, count it, leave the choice to a human).

## 5. Advisory engines (optimizers, rebalancers, forecasts)

- **Advisory first**: nothing is applied and no live state is written; each run lands in its
  own directory with the exact problem it solved. An "apply" path waits until humans have
  read real proposals.
- **Inputs are the day's effective decisions**; items a human fixed today are pinned — "a
  decision somebody made this morning outranks an arithmetic argument against it".
- **Start from the number the user already sees.** Reuse the exact reads and model of the screen
  they trust, so the advisor's "before" equals that screen's figure (pin it with an acceptance
  test); otherwise every proposal opens with an unexplained discrepancy.
- **Cap each unit's gain at its target** — past its plan a unit gains nothing, so its slack
  becomes supply. Weigh units in a common unit (e.g. standard minutes of work) but report the
  headline in the unit people use (pieces, orders).
- **Exclude what cannot be scored wholesale**: a unit missing an input is left out entirely —
  none of its slots offered, none of its people taken — and the report says so.
- **Hard rules** (never stop a running unit; cap any unit's loss; a change budget) and **soft
  costs** (each change must buy a minimum gain; crossing a boundary costs more). The first
  run on real data will reveal a missing rule (an unconstrained search stopped two units to
  feed others for a gain that only existed in the objective's units) — add it and record why.
- **Output = packages + a curve**: split changes into independent packages (any subset is a
  valid state), order them by value per change, so "stop after N changes" is always safe.
  Report a **ceiling** (the best possible), the spread across seeds, and what no move can fix.
- **The browser never scores**: the server precomputes each curve point; a human's what-if is
  re-scored server-side against the run's recorded problem; the client only renders.
- **Verification without an oracle** (see `test-gates` §12): brute-force small instances;
  a fixture per hard rule; parts add up to the headline; an already-optimal input gets no moves.

## 6. Narrow beats global

Prefer an engine that **fills genuine holes** (scored by closeness to the decision it
replaces) over one that re-optimizes everything. A person a decision placed moves only as
part of a complete, **bounded** chain that unblocks a hole (deep ladders are rarely carried
out as written); report the holes a deeper limit would have covered. Global rebalancing is a
*different*, advisory capability.

## 7. One field per question

Keep orthogonal facts in separate fields: `status` = **the problem** (partitions every row;
sums to the total) and `resolution` = **how it was covered** (a subset; never a fifth status
bucket). Consumers read explicit fields; they never parse display text. "When adding a value
to an enum requires teaching every reader a new meaning for an old name, the value belongs
in a new column." When a fix drops a count to zero, ask what that count was carrying (a fix
for false conflicts silenced the only signal of real double-bookings).

## 8. LLMs sit on top of deterministic tools

The chat agent computes nothing itself: it runs deterministic tools and relays their output.
Advisory output is relayed **as a proposal the human decides on, never as a change made**.
Writes go through human confirmation of code-rendered text (see `llm-agent-product`).

## Translation: LangGraph · MCP · FastAPI · React · OR-Tools

| Concept | Your stack |
|---|---|
| Suggestion lifecycle | `proposals` table: `PROPOSED → ACCEPTED/DENIED/REOPENED` rows (decision-ledger) |
| Accept = author | `POST /proposals/{id}/accept` calls the same service function as a manual edit |
| Human-in-the-loop | LangGraph `interrupt()` before any write node; MCP tools read-only + a `propose_*` tool that returns a proposal object |
| Consequence beside the number | API returns `{allowed: true, warnings: ["crosses floor", "stops line 5"]}`; React shows them inline, never blocks |
| Advisory optimizer | OR-Tools CP-SAT for exact answers on small instances (and to measure a heuristic's gap); simulated annealing at scale; run record stored as JSON |

## Checklist
- [ ] The authority stack for your domain is written down (a `docs/decision-authority.md`).
- [ ] Every detector passes the six questions; human-chosen differences are not reported.
- [ ] Suggestions accepted through the manual save path; denials recorded.
- [ ] Advisory engines write nothing live; packages + curve + ceiling; pinned human decisions.
- [ ] Status and resolution are separate fields.

Templates: [references/templates.md](references/templates.md).

## Related skills
`readiness-detectors` · `decision-ledger` · `llm-agent-product` · `test-gates`
