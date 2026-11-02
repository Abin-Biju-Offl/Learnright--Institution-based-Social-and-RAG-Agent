---
name: decision-ledger
description: Model human decisions and captured facts so nothing is ever lost and every reader agrees on what is in force. Covers "never delete information" (exclusion is a recorded decision, never an absence), append-only decision logs where the latest row per subject wins, withdraw/supersede/reopen rows carrying actor, time and reason, status columns instead of deletes, one shared in-force predicate, separating evidence, derived state and human decisions and replaying decisions after every rebuild, keying decisions on durable subjects (not rotating labels or positions), identity vs presence, identity folds at read time, digest-bound companion files, unknown as a first-class value, undoing only the system's own writes, backups as an accident net, and audit trails. Use when designing how approvals, overrides or edits are stored, implementing disable/remove/withdraw/undo, building audit logs, reconciling identities, or whenever a toggle or cleanup might erase data.
---

# Decision ledger: unused is not deleted

> Anything captured — a user's override and the reason they typed, a capture, a superseded
> derived drop, an uploaded input — may be **excluded from a computation**, but must never be
> erased, emptied, blanked or truncated to make a feature "off".

**The shape not to copy:** unticking a "use saved overrides" checkbox wrote an empty list
over the overrides file. Every decision captured that day — and the reasons typed with them —
was destroyed by one click. (The wipe had also been quietly preventing a double-booking,
which is why it looked reasonable for as long as nobody named the alternative.)


**On Postgres · FastAPI:** an append-only `decisions` table (app role may only INSERT/SELECT; triggers refuse UPDATE/DELETE/TRUNCATE), a `decisions_in_force` view with an allowlist of applying statuses, `DELETE` endpoints that insert a `WITHDRAWN` row. Templates §2.

## 1. Classify every table

| Kind | Example | Write pattern | On rebuild |
|---|---|---|---|
| **Evidence** | raw captures, uploads | append; never edited | read |
| **Derived** | canonical tables, caches, reports | regenerated | rebuilt freely |
| **Decisions** | approvals, overrides, withdrawals, assignments | **append-only log** | **replayed over the derived state, in a fixed order** |

- A tenant/module gets write access only when its rebuild provably **replays** the decision
  logs. Prove durability with an actual rebuild: a decision a rebuild undoes is not a decision.
- Overlays on *captured* data (e.g. corrections to attendance) are applied **at read time**,
  never written into the capture.

## 2. Decision rows

Every row: `{subject_key, action|status, value, reason, actor, decided_at, source}`.
- **Latest row per subject wins** (by `decided_at`, then file/insert order as tie-break).
- "Stop applying" is a row: `WITHDRAWN`, `superseded_at`+`superseded_by`, `cleared`,
  `deleted=1` tombstone, `denied`. Undo is a **reopen** row — never deleting the first.
- **A denial is a decision too**: record it ("latest row per suggestion wins"), don't imply it
  by absence.
- An **unknown status applies nothing** (fail closed). A row whose subject cannot be resolved
  is quarantined under its own key and reported, not dropped.
- Headers never narrow: writers take the union of existing and new columns. Rows are kept as
  written — never write a derived value back into a decision row.

## 3. One predicate for "in force"

Two different questions need two different APIs:
- "Does this person/record **exist**?" → read the store.
- "Does this **apply now**?" → `in_force(row)` (status not withdrawn/superseded, effective date
  reached, not tombstoned).

Adding a status column is **fail-open**: every reader that ignores it keeps applying withdrawn
rows (a finder showed people "unassigned" because it read superseded overrides raw). Route
every applying reader through the one predicate and gate the important ones with tests.
Withdrawing is not retiring: marking a person INACTIVE because their last rating was withdrawn
made them look like a leaver.

## 4. Key decisions on durable subjects

- **Not on rotating labels.** A time slot "names a moment, not a group": a decision stamped
  with a slot becomes a statement about a different crew next week. Key on the durable group
  (team/crew); keep the slot as audit data. Relate them in **one resolver that raises** on
  contradiction or ambiguity; readers turn its error into a quarantine.
- **Not on positions.** "Workstation #7" drifts when a station is inserted: a pin followed a
  renumbering onto work the person wasn't rated for. Identify by **what it is** (e.g.
  operation + machine + standard + occurrence index); a pin that cannot be placed becomes a
  caveat, never a fatal error for the whole plan.
- **Standing decisions are date-less** — *when* they apply is the schedule's business.
  "Give the approval an effective date so it matches each day's layout" is the wrong fix for
  any problem.
- **Versions** apply from their date forward, never backward; newest wins *within one
  authoring group*; another group's versions are neither superseded nor consulted.
- **The owning-group column is the decision's identity, not a cache of a member's group.**
  When a person moves group, rows they appear in stay with the plan they were approved in.
- **Migrating a legacy key**: the old stamp is the *boundary* of a group, not its owner —
  regrouping a whole legacy plan unit under one owner destroyed the original grain and made part of
  the plan unsaveable. A row whose group cannot be resolved is quarantined under its own key;
  **refuse** to append onto an unresolvable group (appending put several rows on one slot).
  Re-derive the residue with an audit script, never from a remembered figure.

## 5. Identity is not presence

Identity (who exists), presence (who is here on a date), assignment (who is placed where) and
qualification (who can do what) are different facts with different owners.

- **The filter follows the user's question; the row carries the system's answer.** "Who
  exists / who could do this?" filters on identity (and capability — a rating filter is
  legitimate where a presence filter is not). "Who is here today?" may filter on presence. Every
  row still shows its presence label ("absent", "not captured", "last seen six weeks ago").
- **What a missing presence row means is declared per tenant.** Where captures are complete
  for the people they cover, a missing row means *absent* (shipping "unrecorded" as the default
  once mislabelled every absentee). "Unrecorded" is for "no capture at all for this date" — and
  then **withhold the tally** rather than print "0 present".
- **Counts come off the evidence field, never off the state's display name.**
- **A filter can only remove, so seed the candidate pool from evidence** (present ∪ absent ∪
  the roster) — otherwise a joiner with no roster row is invisible under every filter.
- **A question about the whole scope is asked once (a union), never as a sum of per-group
  answers** — per-group sums over-count people who belong to several groups or none.
- **Date stale or departed people instead of filtering them out**: dropping them deletes the
  evidence that the roster needs cleaning.
- **A narrow predicate used as a scope (rather than on a row) is probably a bug** — a
  `present ∪ absent_on(date)` scope quietly collapsed to present-only.
- **Precedence**: an observed presence beats a paper "absent"; a human correction beats both;
  a correction overlays an existing capture and never invents one.
- Never seen → `days_since_present = None`, not 0.
- **Identity changes resolve at read time**: an alias table with verdicts and evidence is
  produced at ingest; accepted folds are applied when reading, keeping the old id in a
  `superseded_id` column; approval records are never rewritten (an approval made under a
  temporary id sat "approved, applying to nobody" after the id was re-paired). Report records
  that no longer resolve instead of skipping them.

## 6. Unknown is a value

Never invent a plausible default: a copied target is left blank ("a plausible number saved
unread is a wrong target"); unrated is `None`, not 0% ("0% states a measured incapability
nobody observed"); one seat filled out of one is not "100% balanced". "Nobody said" is not
"no". Fail loudly on shapes a reader cannot interpret.

## 7. Bind companion files to the generation they describe

A sidecar describing another artifact (e.g. the movement plan behind a staffing result)
carries the primary's **filename + sha256**. Write the primary first; the reader hashes the
**same byte snapshot it parsed**; if the binding cannot be verified, **withhold** the dependent
view and say so. Write the companion only when it has rows — an empty one reads as
"nothing happened". Order writes so a crash yields "unknown", never "wrong".

## 8. Undo only your own writes

A refused or failed operation decides nothing: remove the rows **it** appended (found by its
own stamp), restore what it replaced, and leave anything anyone else saved meanwhile. If
someone's concurrent edit blocks part of the undo, **say so** instead of reporting "restored".

## 9. Backups are an accident net, not a licence

- Installs keep one prior generation (`.bak-<ts>-<id>`); the decision logs themselves are the
  real history.
- **Preserve-before-destroy is an order**: a refused or failed backup blocks the destructive
  step. Verify backups by **hash**, not size/mtime (a sync tool's "nothing to copy" compares
  size and time, not content). Judge "is this the only copy?" by location, not by name.
- Retention sweeps (log rotation, output expiry) are explicit decisions and never touch
  decision logs or evidence.

## 10. Audit trail

Append one compact JSON line per write: actor, reason, before/after revision, per-subject
before/after values, backups made; flush + fsync. Log **refusals** too. A best-effort audit
must never turn a committed save into a failure — and keep it out of the lock span if you can.

## Translation: Postgres · FastAPI · React

| Concept | Your stack |
|---|---|
| Append-only log | `decisions` table owned by a migration role; the app role gets `INSERT, SELECT` only, plus `BEFORE UPDATE OR DELETE` and `BEFORE TRUNCATE` triggers that raise (templates §2) |
| Latest row wins | `DISTINCT ON (tenant_id, subject_key) … ORDER BY tenant_id, subject_key, decided_at DESC, id DESC`, then an **allowlist** of applying statuses (`status IN ('APPROVED','REOPENED')`) — a denylist is fail-open for every future status (templates §2) |
| DELETE endpoint | `DELETE /x/{id}` inserts a `WITHDRAWN` row (204); `POST /x/{id}/reopen` inserts `REOPENED` restating the value it reinstates |
| Status instead of delete | `status` enum column + the one `in_force` SQL view everybody reads |
| Identity folds | `person_aliases(old_id, new_id, verdict, evidence)`; queries join through accepted aliases at read time |
| Audit | `audit_log` table (jsonb payload) or OpenTelemetry events; refusals included |
| UI | "Remove" shows "Withdrawn by <actor> · Reopen"; never a silent disappearance |

## Checklist
- [ ] Every table classified (evidence / derived / decisions); decisions replayed after rebuilds.
- [ ] "Off", "remove", "undo" implemented as rows, never as deletes or empty writes.
- [ ] One `in_force` predicate; applying readers use it.
- [ ] Decisions keyed on durable subjects (group, identity), not slots or positions.
- [ ] Unknown represented as `None`/unrecorded, never a plausible default.
- [ ] No test asserts a persisted store is empty after an operation.

Templates: [references/templates.md](references/templates.md).

## Related skills
`human-decision-authority` · `safe-writes` · `canonical-data-pipeline` · `test-gates`
