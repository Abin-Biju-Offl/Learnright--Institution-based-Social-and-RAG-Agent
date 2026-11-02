---
name: code-data-boundaries
description: Draw and enforce the boundaries that keep code, data, secrets, runtime state and contributor tooling from leaking into each other. Covers the "two truths" model (code's truth is version control and ships as an immutable artifact; data's truth is the running system and flows up to backup, down only for gated recovery), the product-vs-workbench audience axis (what ships vs what only builders need), the lockstep between VCS-ignore and deploy/Docker-exclude lists, data trees outside the code tree with derived data nested inside the data tree, runtime-writable paths as part of the deploy contract, and tests that ask the transfer tool what actually ships. Use when laying out a new repository, adding a generated artifact/cache/output, adding docs or agent tooling, deciding where data lives, designing backup and restore direction, or writing a Dockerfile/.dockerignore.
---

# Code–data boundaries: two truths and one audience axis

> Conflating code and data is the #1 way to break a deploy: a code push overwrites live
> data, data leaks into git, or a "deploy" restores a stale backup over fresh captures.

## 1. Declare a source of truth and a direction for every class of artifact

| Class | Source of truth | Routine direction | Transport | Never |
|---|---|---|---|---|
| **Code** | version control | repo → host | immutable artifact built from a commit (`git archive`, image by digest) | ship a working tree; run git on the host |
| **Data** (per tenant): raw captures + derived tables | the **running system** (it captures and humans decide there) | host → backup, additive, ~2×/day | object-store sync / DB backup | push down routinely; prune by default |
| **Recovery** | backup | backup → host, **once** | a separate, gated command | run while services are up; run from any deploy path |
| **Secrets** | secret manager (versioned) | rendered per host at deploy | root-owned env file / runtime secret | live in the repo tree; be hand-edited on the host |
| **Runtime state**: locks, sessions, logs, outputs | the host | stays local | — | ride a code push; be wiped by `--delete` |
| **Workbench**: builder docs, agent rules, CI | version control | never ships | — | reach production |

**Single ingress.** A trusted workstation (or CI) is the only way in to a host, for code and for
recovery data alike. The host's only autonomous outbound action is pushing *its own* data to
*its own* backup; it never pulls code or data by itself.

Derived data is **data**, not code: it lives *inside* the data tree (e.g. `<data-root>/canonical/`),
and the backup mirrors the whole tree 1:1. Placeholder values (e.g. a bucket named
`REPLACE-ME`) **fail closed**.

## 2. Layout

```
<parent>/
  <app>/                      # the repo — code + workbench, NO data
    core/ contract/ tenants/<id>/ app/ deploy/ scripts/ tests/
    docs/ CLAUDE.md AGENTS.md LOG.md README.md SPEC.md   # workbench (never ships)
    deploy/RUNBOOK.md                                     # ships: the 3am operator needs it
  <app>-data/<tenant>/        # one data tree per tenant, outside the repo
                              # (on a host: /srv/app-data/<tenant>/)
    raw/...                   # captures: append-mostly, per (source, key, date)
    canonical/                # derived, rebuilt by the adapter; decisions replayed into it
    decisions/                # human decision logs (see decision-ledger)
```
The code resolves data roots from env vars named in the tenant manifest; a repo-local
default exists only for development and should **fail loudly** on a production host
(read-only filesystem) rather than silently write into the code tree.

## 3. The lockstep rule

A new generated artifact (cache, scratch CSV, run output, derived tree, staging dir) goes
into **both** the VCS ignore list **and** the deploy exclude list (and `.dockerignore`), in
the same commit. One without the other means it either rides a production push or gets
committed. Put a comment in each list pointing at the other, and **test set equality** of
the data/secret/runtime block — spot-checking a few entries lets new ones drift.

## 4. The audience axis: product vs workbench

**Would production at 3am be worse off without this file? No → workbench.** It stays in
git and is excluded from the deploy artifact.

- **Read-denied is not workbench.** Code the product executes but its agent may not *read*
  (core engine, contract) must still ship. Only builder-facing docs are workbench.
- **The runbook ships** — its audience is the operator on the host. The axis is about
  audience, not file type.
- A deploy exclude list is a **denylist: every new file ships by default.** Either keep the
  workbench block current (anchored patterns, tested) or build the artifact from an
  allowlist of product paths.
- Excluding a path does **not** remove it from hosts that already have it (`rsync --delete`
  skips excluded paths). Clean old hosts once, by hand; never put a standing `rm -rf` in
  the deploy path for a one-time transition.

## 5. Runtime-writable paths are part of the deploy contract

Hosts run with a read-only filesystem (systemd `ProtectSystem=strict`, container read-only
root). Every path the process writes at runtime must be granted (`ReadWritePaths=`, a
volume) **and pre-created** — an ungranted write fails with EROFS, and many frameworks
swallow handler exceptions, so it fails **silently** in production while every local test
passes. Derive the expected grants in a test from the code's own path constants; order
side effects so a sandbox failure is cosmetic (audit append after the install, non-fatal).

## 6. Exclusion gotchas (each one bit a real deploy)

- **Anchor** workbench patterns (`/README.md`): unanchored, `README.md` matches at any depth
  and nested product docs silently stop shipping.
- `.git` and `.venv` **without** a trailing slash: in a worktree `.git` is a file and `.venv`
  may be a symlink; `.venv/` misses the symlink and `--delete` then dismantles the host's
  real virtualenv.
- If the service user's `$HOME` is inside the sync destination, exclude its dotfiles
  (`.config/ .cache/ .local/ .ssh/`) — or a routine push deletes the credentials the backup
  timer uses.
- Per-tenant secret files are secrets even when hand-made: ignore + exclude them, or every
  tenant's tokens land on every host.
- After narrowing what a tenant's artifact contains, delete the now-excluded stale packs on
  the host explicitly.

## 7. Test what actually ships — ask the tool

If production behaviour is "rsync / docker decides", the test must ask rsync / docker.
- Dry-run the real transfer (`rsync -an --out-format=%n` with the real exclude array, or
  `docker build` context listing) and assert: workbench paths absent, must-ship paths present
  (core engine, contract, the runbook), secrets absent.
- Keep the guarded entries as a **literal tuple in the test** — a test that reads the list it
  guards cannot see the list shrink.
- Assert the product agent discovers nothing from the filesystem (see `llm-agent-product`).

Templates: [references/templates.md](references/templates.md).

## 8. Data never flows down as a routine step

No feature or script may push data onto a running host routinely — it clobbers live
captures and human decisions. The restore command: refuses while the services run,
requires typing the tenant id, stages on a trusted workstation, and is never called by a
deploy. Provisioning restores data only when it **creates** the host or is given an
explicit `--restore` flag; otherwise it prints "preserving the host-owned data".

## Translation: Docker · Cloud Run · Postgres · GitHub Actions

| Concept | Reference stack | Your stack |
|---|---|---|
| Code artifact | `git archive <sha>` → rsync | image built **from a clean checkout of `<sha>`** (or `git archive`) in CI; tag = sha; label `org.opencontainers.image.revision` |
| Deploy exclude list | `SHIP_EXCLUDES` | `.dockerignore` (lockstep with `.gitignore` for data/secrets; workbench block for docs, `.claude/`, `.github/`) |
| Read-only FS + grants | `ProtectSystem=strict` + `ReadWritePaths=` | `read_only: true` + named volumes / `tmpfs` (compose); Cloud Run: only `/tmp` (in-memory) — state goes to Postgres/GCS |
| Data truth | the host's data tree | Postgres (+ object storage): migrations are **code**, rows are **data**; backups/PITR flow up; restore is a gated runbook; seed scripts never target prod |
| Secrets | rendered env file | Secret Manager / Key Vault mounted as env at runtime; `.env.example` documents knobs |
| Workbench | excluded from rsync | excluded from the image; never mounted |

## Checklist
- [ ] Every artifact class has a declared source of truth and direction.
- [ ] Data trees live outside the repo; derived data nested in the data tree.
- [ ] Ignore list and deploy/Docker exclude list move in lockstep (set-equality test).
- [ ] Workbench block anchored and tested by dry-running the real transfer.
- [ ] Every runtime write path granted, pre-created, and test-derived from code constants.
- [ ] Restore is a separate, gated command; no deploy path moves data down.

## Related skills
`release-provenance` · `hardened-runtime` · `canonical-data-pipeline` · `agentic-workbench` · `llm-agent-product`
