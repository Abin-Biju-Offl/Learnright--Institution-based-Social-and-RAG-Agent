---
name: release-provenance
description: Ship only reviewed code to production as an immutable artifact whose identity the target remembers, then verify what is actually running. Covers the release line (only commits reachable from protected main; an older ancestor is the rollback), artifacts built from a commit (git archive or an image by digest), the full gate run by the production wrapper with skips recorded, a two-phase provenance manifest (commit, tree, channel, scope, gate status, secret version, phase, time), channels (production, development, one named break-glass), per-target consent one target at a time, a fleet reader comparing the recorded claim with the live fact, honest exit codes, data-before-code migrations, and testing deploy scripts with fake tools in throwaway repos. Use when designing CI/CD or deploy scripts, adding environments or tenants, building a what-is-deployed-where view, or writing a break-glass procedure.
---

# Release provenance: tested, merged and deployed are one traceable line

> The first time anyone read the deployment records back, production hosts had **no
> record at all** and were dozens of commits behind. A record with a writer and no reader
> is write-only — not a control.


**On GitHub Actions · Cloud Run / Container Apps:** build the image from the merged commit, gate on fast + acceptance, deploy by digest behind a GitHub Environment approval per target, keep immutable facts in revision labels and the phase in a releases table, and run a fleet check that compares serving revisions with `main`. Templates §3.

## 1. The release line

- Production deploys **only commits reachable from the protected main branch**:
  `git fetch origin && git merge-base --is-ancestor HEAD origin/main`. Refuse anything else
  before any byte moves. Any *older* ancestor is accepted — that is the rollback path.
- Deploy from the **primary checkout on main, pulled `--ff-only`** — never a feature branch
  or an agent's worktree (standing on an old ancestor silently rolls production back).
- Git flow: issue → branch → PR → required CI (fast suite) → review → merge → update local
  `origin/main` → **full promotion gate** → deploy.

## 2. Ship an artifact, never a working tree

- Build from the commit: `git archive "$SHA" | tar -x -C "$(mktemp -d)"`, then transfer *that*
  (or build an image from a clean checkout of `$SHA`, tag it with the sha, deploy **by digest**).
  Uncommitted edits can then never reach production.
- Resolve the tenant scope from the artifact itself, ship only that tenant's pack, and delete
  stale excluded paths on the host explicitly (`rsync --delete` keeps excluded paths).
- The host has no git: the artifact's identity must be **written down on the host** (§4).

## 3. The gate runs inside the production wrapper

- Require a clean tree; run the **full** gate (fast + acceptance); record `passed`.
  `--skip-tests` is allowed but records `skipped` **permanently**.
- Resolve the secret/config source **before** the gate (a missing secret should cost seconds,
  not a ten-minute gate).
- Hosts never re-run tests: dependency parity comes from pinning (`constraints.txt` frozen from
  the environment that passed the gate; hosts install with `-c`). A host once ran a different
  Python minor "by accident" and an unpinned rebuild would have jumped a major library version.

## 4. The provenance manifest

A key=value file at a fixed path outside the code tree (e.g. `/etc/<app>/release.env`,
mode 0644 inside a 0750 root-owned dir, **no secrets**):

```
RELEASE_COMMIT=…        RELEASE_TREE=…          RELEASE_SCOPE=<tenant>
RELEASE_CHANNEL=production|development|emergency
RELEASE_GATE=passed|skipped|unknown
RELEASE_CONFIG_SOURCE=file:<name>|secret:<name>#<version>
RELEASE_EMERGENCY_REASON=…   RELEASE_PHASE=transferred|healthy|unhealthy
RELEASED_AT=<UTC ISO>
```
- **Validate every input before the first mutation** (a typo in the gate status once deployed
  code while leaving the *old* commit recorded).
- Write **atomically** (temp + rename) — a failed write must not truncate the last honest record.
- **Two phases**: `transferred` immediately after the transfer; `healthy` only after the
  restart **and** a health check with bounded retries. A failure in between leaves
  `transferred` — so a half-finished deploy is distinguishable from a good one.
- **One writer** for the manifest (a second ad-hoc `sed -i` writer drifted).
- Fix a permanently-wrong status immediately: a phase that always read "not restarted" trained
  everyone to ignore it, so a real half-deploy would have looked normal for weeks.

## 5. Channels

| Channel | Accepts | Recorded as |
|---|---|---|
| production (default, fails closed) | commits on the release line | `production` |
| development | an unmerged commit → **non-production targets only** | `development` |
| break-glass (one named path) | an unreleased commit in an incident: clean tree, **full gate**, a bounded safe-text reason (`^[A-Za-z0-9][A-Za-z0-9 ._:/#-]{7,159}$`); refuses `--skip-tests`, a dirty tree, and an already-released commit | `emergency` + reason |

After break-glass: reconcile the commit through a normal PR and write a journal entry. Rollback
and break-glass stay **human runbook procedures**; agents never run them.

## 6. Consent and sequencing

- An explicit **yes per target**, in the current conversation/session; consent never transfers.
- **One target at a time**; stop the sequence on any non-routine signal.
- Each tenant has a wrapper that fixes the scope (and refuses an override); interactive runs
  ask the operator to type the host name; `--yes` exists for an operator who already consented.
- **Config changes go through the full wrapper** — a code-only sync does not re-render config, and
  a newly documented key "deployed cleanly and changed nothing".
- **A restart interrupts a person.** Schedule deploys around active sessions and capture
  cadences: a restart in the middle of a capture or a save turns someone's save into a refusal.
- **Half a fleet is the normal failure.** A change is live only when every target has been
  redeployed and read back; until then, say which targets run what.

## 7. Read it back: claim vs fact

A **read-only fleet reader** probes each host (read the manifest, the supervisor's live state,
the derived-data marker) and classifies against local `origin/main`:

`current` · `behind N` (rollback or unpulled? — it refuses to guess) · `not-on-main` ·
`unknown-commit` · `no-record`

…plus concerns: channel not production, gate not passed, phase not `healthy`, scope mismatch,
**runtime inactive now**, data stale. Exit 0 all current and live · 1 drift · 2 unreachable.
Code placed on a host by hand (outside the wrapper) makes the manifest lie — and the reader then
reports a stale claim as fact; if you ever must, record it on the host in the same breath.
**The manifest is a claim made at deploy time; the supervisor is the fact now.** Never report
"deployed" on an exit code alone: `SHIPPED` · `SHIPPED, RUNTIME UNVERIFIED` · `NOT SHIPPED`
· `ESCALATE TO HUMAN`.

## 8. Data before code

A store-layout migration is a **one-time act with a human reading its output** — never something
a wrapper does silently on the deploy path. Sequence: sync the code **without restarting** →
run the migration as a dry run → read its report → migrate (add-only, idempotent, the old layout
kept and frozen) → restart. Provisioning/validation **stops before validating** a store that is
still unmigrated and names the migration to run. After deploy, a derived-data provenance marker
that is stale (built by older code) produces a warning and a rebuild prompt — new adapter code
once sat inert behind data built hours earlier, while validation (a property of bytes) passed.

Know the marker's trade-off: it fingerprints the adapter code, not the whole shared core, because
a warning that fires on every deploy gets scrolled past. Coverage vs alarm fatigue is a choice —
record which side you took.

## 9. Honest signals

- Redirect deploy output to a log; **nothing after the wrapper** on its line (`| tail`,
  `; echo $?` and `&&` all misreported failures as success). Read the exit code from the log.
- Health checks retry with a bound: a single probe raced the service bind, made every deploy
  exit non-zero, and taught operators that a red deploy is normal.
- Pin the procedure's load-bearing lines with tests (see `agentic-workbench` §8).

## 10. Test the deploy scripts themselves

Shell scripts that ship production are code. Test them from the fast suite:
- a **throwaway git repo** modelling the release line (main, a merged commit, an unmerged branch,
  a dirty edit);
- **fake `rsync` / `ssh` / `gcloud` / `systemctl` on `PATH`** that record their arguments and
  model real quirks;
- assert: an unmerged commit is refused **and no bytes are transferred**; the artifact contains
  committed bytes, never the dirty edit; call order `manifest(transferred) < chown < restart <
  manifest(healthy)`; a failure after transfer leaves only `transferred`; break-glass
  refuses a dirty tree; `bash -n` passes on every script; renderers are tested by **running** them.

## Translation: GitHub Actions · Docker · Cloud Run / Azure Container Apps

| Concept | Your stack |
|---|---|
| Release line | build only on `push: main`; the deploy job verifies `git merge-base --is-ancestor $SHA origin/main` |
| Artifact | image built in CI from the commit, tagged `sha-<short>`, deployed **by digest** |
| Gate in wrapper | deploy job `needs: [fast, acceptance]`; record the result |
| Provenance | Cloud Run revision labels/annotations (`commit`, `tree`, `channel`, `gate`, `env-version`); image label `org.opencontainers.image.revision` |
| Two phases | revision labels carry only immutable facts (commit, channel, gate); record the phase (`transferred` → `healthy`/`unhealthy`) in a `releases` table or the GitHub Deployments API — relabelling a service can roll a revision that was never health-checked |
| Consent per target | GitHub Environments with required reviewers, one environment per tenant/target |
| Break-glass | a `workflow_dispatch` with a required `reason` input, an approval environment, `channel=emergency` recorded, a follow-up issue opened automatically |
| Read-back | a script calling `gcloud run services describe` / `az containerapp revision list` per target, comparing the serving revision's `commit` label to `origin/main` and checking it is healthy |
| Rollback | shift traffic to the previous revision (same labels), never rebuild from a branch |

## Checklist
- [ ] Production refuses commits outside the release line, before any transfer.
- [ ] The artifact is built from the commit; never a working tree.
- [ ] The wrapper runs the full gate on a clean tree; skips recorded permanently.
- [ ] Manifest validated, atomic, two-phase, single writer, no secrets.
- [ ] One named break-glass path; rollback is an older ancestor through the same wrapper.
- [ ] A fleet reader compares claim vs fact; outcome taxonomy used in reports.
- [ ] Deploy scripts tested with fake tools in a throwaway repo.
- [ ] Store migrations are human-run (dry run first); deploys scheduled around active work.

Templates: [references/templates.md](references/templates.md).

## Related skills
`hardened-runtime` · `code-data-boundaries` · `test-gates` · `agentic-workbench` · `multi-tenant-platform`
