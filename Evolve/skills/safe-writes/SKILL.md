---
name: safe-writes
description: Make concurrent writes to shared state safe, attributable and recoverable without a big lock. Covers atomic replace (temp + fsync + rename), one cross-process lock per tenant shared by every writer with a bounded wait and a typed busy refusal, the install guard (compute with no lock, then lock, re-probe the inputs' revision, install or discard), optimistic concurrency scoped to what the edit owns (row digests, per-subject tokens, per-item from/to deltas), server-side merge under the lock, multi-file installs with rollback and one backup generation, typed refusals that name what moved and never cost the user's edits, a refusal log, batch edits in one transaction through one validator, idempotency, and an append-only audit. Use when several users, jobs, bots or processes write the same files or rows, when implementing save/approve endpoints or background solvers that install results, or when users complain that saves get refused or edits get lost.
---

# Safe writes: lock the install, never the work

> A refusal that told users to "reload before saving" was the most common complaint from the floor — and the
> advice to reload was the one action that destroyed the user's edits.


**On FastAPI · Postgres:** a `version` column and `If-Match` for optimistic concurrency; `SELECT … FOR UPDATE` on the rows a save owns; `pg_advisory_xact_lock` only for tenant-wide installs; domain exceptions rendered by one handler; TanStack Query replays edits after a 409. Templates §7, translation table at the end.

## 1. The write protocol, end to end

```
validate (pure, reads nothing live)          ← before the lock: fail fast, cheap
baseline = revision(inputs this save owns)   ← refuse now if client's expected revision differs
compute / stage   (NO lock: solvers, rebuilds, rendering into a sibling temp dir)
with tenant_lock:                             ← milliseconds
    if revision(inputs) != baseline: refuse "moved — nothing applied"   (the real check)
    merge: every live row not mine + my rows
    install staged files (atomic, with one backup generation, rollback on failure)
audit (append, fsync; failure never fails the committed save)
queue follow-up work (after release; never inside the save)
```

## 2. Atomic replace

Write to a temp file **in the same directory** (dot-prefixed, uuid-suffixed), flush,
**fsync**, `os.replace`. Readers see the whole old file or the whole new one. Staged files
written into a temp dir under the live parent stay on one filesystem, so the rename is atomic.

## 3. One lock per tenant, shared by every writer

- The web console, the chat bot's file ingest, scheduled rebuilds and unattended jobs all take
  **the same lock file** for a tenant. Two implementations "kept in sync by the filename" is a
  latent bug — share one module.
- Bounded wait (≈5 s, polling), then a typed **Busy** refusal (→ 503 + code); the client keeps
  the user's edits. A fresh `open()` per acquisition makes threads contend exactly like
  processes (`flock` is per open file description).
- **Not re-entrant**: never call lock-taking code while holding the lock (a follow-up job
  started inside a save deadlocked against it) — queue follow-ups after release.
- Unattended jobs call **the same service function** as the UI button, so they obey the same
  lock and checks.
- Cross-process admission slots (e.g. "one extraction job at a time") use a lock file too —
  an in-process semaphore is silently duplicated by `fork`.

## 4. Lock only the install (the install guard)

A three-minute solve that held the tenant lock stalled every other editor and made the bot's
non-blocking ingest fail. Instead: baseline → compute unlocked → `guarded_install(probe,
baseline)` → install or discard. Solving outside the lock costs a **rare, explainable retry**;
solving inside it cost everyone a multi-minute stall. `probe` is a callable so callers can
narrow its scope (per unit, per subject) without changing the primitive.

The rule that decides how narrow you may go: **re-validate under the lock and you may scope
to your own rows; compute outside it and you must guard your whole input set.**

## 5. Precondition at the grain of the edit

Whole-file hashes refuse edits that never overlapped — two editors on different units always
collided, and a feed rewriting files every minute made almost every save stale.

| Grain | Mechanism | Use when |
|---|---|---|
| **Rows** | digest of the rows matching the save's key (skip blank values so schema widening isn't a change; hash the row count; a missing file = zero rows; unreadable → raise) | edits own a slice of a shared table |
| **Subjects** | per-subject tokens (`{person:102: "9f3a…"}`); client echoes `expected_subjects`; refusal returns the **current tokens** so the form adopts them without another request | forms editing a few named entities |
| **Items** | each change carries `from` → `to` + the item identity; a colleague who set the same value is agreement, not conflict | dense grids |

- Keep a whole-revision fallback for old clients — **narrowing never removes a guard**.
- Preconditions **bypass every cache**: a precondition is exactly where a stale answer does damage.
- Re-homing person A must never refuse a certification for person B — test cross-subject independence.

## 6. Typed refusals that keep the work

| Exception | HTTP | Body |
|---|---|---|
| `UserError` (ValueError) | 400 | `{error}` — user-correctable |
| `PermissionDenied` | 403 | `{error}` |
| `SessionTokenExpired` | 403 | `{error, code: "session-token-expired"}` — client re-fetches the token and retries once |
| `Stale` | 409 | `{error, code: "stale-…", subjects: {…current tokens}}` |
| `Busy` | 503 | `{error, code: "busy"}` + `Retry-After` |
| `TooLarge` | 413 | `{error}` |
| anything else | 500 | generic text; the real error goes to the log only |

- **Messages state facts only** ("Someone saved unit 4 after you opened it, so nothing was
  applied") — never "Reload". Only the client knows whether it recovered the edits.
- One exception → status table for the whole server. Duplicated per-service exception classes
  drift: a missing one quietly turns a 409 into a 400.
- **Log every refusal** (route, code, tenant, actor, message — and the typed values if they
  may have nowhere left to go). The refusal rate is how you know whether preconditions are
  scoped right.

## 7. Client-side conflict replay

On refusal: diff the user's edits against the baseline they opened → reload → re-apply each
edit to rows **nobody else changed** → report rows someone else changed (theirs stands) and
rows that vanished → **never auto-save the merge**; mark the screen dirty so the user
re-approves what they can see. Any new piece of client state joins this recovery path in the
same change — "anything reset by load is something a refusal will destroy".

## 8. Installs, backups, batches, idempotency

- **Multi-file install**: back up each live file (one prior generation), `os.replace` each
  staged file, roll back what was installed if one fails, then prune older backups. Readers
  don't take the lock, so they can briefly see table A new and table B old — if that matters,
  install a single generation pointer instead (a `CURRENT` file or a DB view switch).
- **Batch edits in one transaction**: one lock, one revision check, one backup generation, one
  audit record; the single-item path **delegates to the batch path**, so there is one validator.
- **Idempotency**: uploads dedupe on `(tenant, intent, sha256)`; retried requests carry an id.
- **Audit**: append-only JSONL (or table) with actor, reason, previous/new revision, backups,
  per-subject before/after; fsync; a failed audit never fails a committed save.

## 9. Background follow-ups

Never compute "best-effort" extras inside a save (one helper solved many items at seconds each
inside a save — a multi-minute hang). Queue them: one job per tenant, run when the server is
idle, at low priority, **always release the slot in `finally`**, credit the work to the right
actor, and let the install guard re-validate each result.

## Translation: Postgres · FastAPI · React

| Concept | Your stack |
|---|---|
| Tenant lock | `SELECT pg_advisory_xact_lock(hashtext('tenant:'||$1))` for tenant-wide installs; plain row locks (`SELECT … FOR UPDATE`) scope naturally to rows |
| Optimistic concurrency | `version` column: `UPDATE … SET …, version = version + 1 WHERE id = $1 AND version = $2` → 0 rows = 409 |
| HTTP preconditions | `ETag` per resource/subject + `If-Match`; 412/409 with current ETags in the body |
| Compute unlocked | run the solver outside the transaction; in the transaction re-read the input versions and compare |
| Busy | `lock_timeout`/`NOWAIT` → 503 + `Retry-After` |
| Error taxonomy | FastAPI exception handlers mapping your exception classes → status + `code` |
| Conflict replay | TanStack Query: on 409, refetch, re-apply local edits to untouched rows, flag conflicts, keep the form dirty |

## Checklist
- [ ] Every writer process shares one tenant lock implementation; bounded wait; typed Busy.
- [ ] Expensive work happens with no lock; install guarded by a re-probe.
- [ ] Preconditions scoped to rows/subjects/items; refusal returns current tokens.
- [ ] Refusal messages never say "reload"; client replays edits; refusals are logged.
- [ ] Batch and single paths share one validator; audit append never fails a save.

Templates: [references/templates.md](references/templates.md).

## Related skills
`decision-ledger` · `console-backend` · `canonical-data-pipeline` · `touch-ui-system`
