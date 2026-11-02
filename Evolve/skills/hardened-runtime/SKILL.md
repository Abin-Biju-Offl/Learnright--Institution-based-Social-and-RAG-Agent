---
name: hardened-runtime
description: Run services on VMs or containers so failures are loud, bounded and recoverable. Covers systemd units with the sandbox as a write ceiling (ProtectSystem=strict, pre-created ReadWritePaths derived from code constants, metadata IP denied), per-tenant drop-ins masking other tenants data, secrets rendered from a versioned secret store through an allowlist, templated timers and chains (explicit time zones, coalescing, ExecStartPost --wait, never started-by plus After=, non-idempotent delivery on its own timer), one OnFailure alert template with a dependency-free notifier and loud non-delivery, watchdogs that probe the function, memory and log ceilings, idempotent provisioning that verifies before restart, and tests for units and scripts. Use when deploying services to VMs, writing systemd units or timers, setting up alerting or watchdogs, handling host secrets, or containerizing with a read-only filesystem.
---

# Hardened runtime: loud, bounded, recoverable

> `systemctl is-active` reported "active (running)" for most of a day while the network
> tunnel the service depended on was down. Health is the function working, not the process existing.


**On Cloud Run / Container Apps:** see §10. Least-privilege service accounts instead of IP blocks; scheduled jobs that take an advisory lock (jobs don't coalesce); explicit time zones; min-instances + startup probes to warm; alerts on job failures, restarts and a dependency-probing health check.

## 1. The sandbox is a write ceiling

```ini
[Service]
User=app
Group=app
WorkingDirectory=/opt/app
EnvironmentFile=/etc/app/app.env
# or the journal looks silent while the process is fine
Environment=PYTHONUNBUFFERED=1
# the code tree is read-only
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/app/.venv/bin/python -m app.server
# often the ONLY supervision an unhandled crash gets
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
# whole FS read-only except the grants below
ProtectSystem=strict
ReadWritePaths=/var/lib/app/locks /var/log/app /var/lib/app/outputs
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
MemoryDenyWriteExecute=true
CapabilityBoundingSet=
UMask=0027
# the cloud metadata endpoint: the top SSRF target
IPAddressDeny=169.254.0.0/16
```
- **Every runtime write path is granted and pre-created.** `ReadWritePaths=-/p` with a missing
  `/p` is *skipped*, not created; without the `-`, a missing path stops the unit from starting.
  An ungranted write fails with EROFS — and frameworks that swallow handler exceptions make it
  **silent** in production.
- Derive the expected grants **in a test from the code's own path constants** (lock dir, audit
  log, outputs) and check every unit that runs that code, including indirect ones.
- Split units by write scope: irreplaceable inputs (captures) · re-derivable outputs (derived
  data) · re-fetchable caches. The web unit gets the raw tree **read-only**.
- Split units by **network scope and blast radius** too: the one step that needs a privileged
  endpoint (e.g. the metadata server for cloud credentials) becomes its own unit instead of
  widening the capture's network policy, and is pulled in with `Wants=` so its outage can't
  cost the capture.
- Redirect SDK/library state directories into granted paths (an agent SDK that writes session
  state under `$HOME` failed on the first save).
- The sandbox is a ceiling **under** application authorization, never a substitute for it.

## 2. Per-tenant scope as a drop-in

The base unit grants **no** tenant data roots. Setup generates
`/etc/systemd/system/app.service.d/10-scope.conf` with `ReadWritePaths=<own root>` and
`InaccessiblePaths=-<every other known root>` — a stale, wider deploy can never widen access.

## 3. Secrets: a rendered build product

- Source precedence: an explicit `--env-file` (must exist — a missing one is a typo, never a
  fallback) → a per-tenant source file → the secret manager. A generic developer `.env` never
  shadows a tenant's real secret.
- Resolve the secret manager's `latest` **once**, pin the version, record it in the deploy
  manifest; probe readability **before** the gate.
- The **secret holds the source**; a renderer on a trusted workstation produces the host file
  through an **allowlist**: copy known keys only when non-empty; tenant-specific secrets only for
  the tenant in scope; **omit** (don't blank) out-of-scope lines; filter admin maps by tenant;
  refuse to render if the selected provider has no credential; write 0600; never print values.
  Warn when a source key is dropped by the allowlist (otherwise a documented setting "deploys
  cleanly and changes nothing").
- Install `root:app 0640` at `/etc/app/app.env`; shred temp copies on both ends; re-render on
  every deploy so a hand edit on the host is reverted.

## 4. Scheduled work: templated units, timers, chains

- **Templated units** (`capture@.service` + `capture@morning.timer`): one unit per instance means
  an overlapping trigger **coalesces** into the running job instead of stacking.
- `AccuracySec=1s` (the default smears minute-level schedules); several `OnCalendar=` lines to
  cross an hour boundary; **explicit time zone** suffixes, each validated with
  `systemd-analyze calendar` at install; never rely on the host's time zone.
- `Persistent=true` for captures (catch up a missed run); `Persistent=false` + `Mon..Sat` for
  reports (no replay after a reboot).
- **Chains**: `ExecStartPost=-+/usr/bin/systemctl start --wait derive@%i.service` — `+` makes only
  that line privileged, `-` keeps a downstream failure from turning the capture red (the child
  has its own `OnFailure`), `--wait` keeps the parent "activating" so `After=` on later units
  orders after both.
- **Invariant**: a unit is either started by the parent's `ExecStartPost` **or** `After=` the
  parent — never both (that deadlocks).
- Idempotent steps may ride a repeating chain; a **non-idempotent delivery** (a chat post, an
  email) gets its own timer ordered `After=`. Ordering is a dependency edge, not a wall-clock gap.
- Map "retry later" (lock busy, inputs moved) to `SuccessExitStatus=75` so it doesn't page.
- Keep schedule guarantees in code too (skip Sundays, refuse stale data) — a deleted timer once
  took its no-Sunday rule and its no-replay rule with it.
- Converge: disable **and delete** unit files no longer shipped (`disable` can't reach a unit
  whose file is gone).

## 5. Alerting: one hook, loud non-delivery

- Every alerting unit: `OnFailure=app-alert@%n.service`. The alert template itself has **no**
  `OnFailure` (no loops) and runs a **stdlib-only** notifier (it must work when the venv is what broke).
- Keyed cooldowns (e.g. 30 min) stored in a preserved runtime dir; `--clear` on recovery re-arms
  the key; escalations use a different key so an earlier alert cannot mute them; prefix the host;
  truncate; retry on 429.
- **Non-delivery is loud**: a notifier that exits 0 without delivering, with its output sent to
  `/dev/null`, meant every watchdog alert for weeks went nowhere. Print `ALERT NOT DELIVERED`
  and check it.
- A unit that composes its own messages loads `EnvironmentFile=` itself (`OnFailure` runs in the
  alert unit's environment, not the failed unit's).
- The supervisor reports **failures**; producers report **outcomes** ("restored in 16 s", "first
  successful run today"). Silence must be distinguishable from success.

## 6. Watchdogs check the function

Probe the observable outcome (interface up with an address, port answering, a write probe) —
never `is-active`. Repair cheap-first (restart, wait), then reliable (explicit reconnect, wait),
judging each step **by the outcome**; keep a cooldown in state that survives runs (≤1 repair per
10 min); cap attempts; escalate in words; provide `--dry-run`; exit 0 with "nothing to watch" on
hosts where it doesn't apply. Dependents use `Wants=` (never `Requires=`) so a failing watchdog
can't block them. Keep secrets away from vendor binaries (`env -u TOKEN …`).

## 7. Ceilings that don't depend on every component behaving

- **Logs**: a journald drop-in (`SystemMaxUse=200M`, `SystemMaxFileSize=50M`); edit the distro's
  logrotate stanza **in place**, idempotently, and verify (two stanzas for one path rotate
  nothing); app logs with `copytruncate`; a retention timer for outputs. A host nearly filled its
  disk from one misconfigured agent's error spam.
- **Memory**: `MemoryHigh=55%`, `MemoryMax=70%` (percentages: one unit, many VM sizes),
  `MemorySwapMax=0`, `MALLOC_ARENA_MAX=2`, `KillMode=control-group`; small swap as kernel
  headroom with low swappiness. `Restart=on-failure` hid repeated OOM kills until the host wedged;
  a per-service cgroup cap keeps the kill local, visible and alertable.
- **Verify the telemetry pipeline end to end** — the host that ran out of memory had no memory
  metrics because the monitoring agent lacked one permission. `Restart=on-failure` turns crashes
  into blips: alert on restart counts too.

## 8. Provisioning: idempotent, verified, convergent

- Describe-then-create every cloud resource; **assert the identity** of existing ones (service
  account, scopes) and fail on mismatch.
- Add IAM bindings without rewriting the policy; never drop a condition or widen a privilege to
  make an error go away.
- An empty backup bucket requires an explicit `--seed`.
- Setup is safe to re-run: swap only if none; the required interpreter version is **checked
  before stopping services**; the venv is rebuilt only on a version mismatch; stale units removed;
  the env template is created only if absent.
- **Verify before restart**: imports, `systemd-analyze verify`, active cloud identity, data
  validation, data provenance. After restart, poll health with a bounded retry.

## 9. Test the infrastructure as code

- Parse unit files **by section, ignoring comments** (comments quote the very settings they
  explain; a check was once satisfied by a comment, then by an inert copy in the wrong section).
- Assert timer fire times as an expanded **set**; assert the started-by/After invariant as a rule
  over all units; assert memory relations (`High < Max ≤ 80%`, swap 0).
- Run scripts with **stub tools on `PATH`** (`ip`, `systemctl`, `journalctl`, the notifier) that
  model real quirks; run idempotent scripts three times and diff.
- **Fail any `Directive=value  # comment` line.** systemd treats `#` as a comment only at the
  start of a line; an inline comment makes the value invalid, the directive is ignored, and the
  sandbox (or `Restart=`, or `EnvironmentFile=`) silently disappears. Run `systemd-analyze verify`
  on every unit in CI.

## 10. On a container platform (Cloud Run · Azure Container Apps)

The principles hold; the mechanisms change.
- **Write ceiling**: the container filesystem is ephemeral — state lives in Postgres / object
  storage; only `/tmp` (memory-backed) is writable.
- **Identity, not IP blocks**: the metadata endpoint can't be blocked (ADC needs it), so the
  control is a **least-privilege service account per service**. Deploy with
  `--no-allow-unauthenticated`, internal or load-balanced ingress, `--max-instances` and
  `--memory` set explicitly.
- **Warm before serving**: `--min-instances` plus startup CPU boost, and a startup probe that
  builds the first screen's caches (the equivalent of warming before fork).
- **Scheduled work**: Cloud Scheduler (explicit `--time-zone`) → Cloud Run Jobs / Container Apps
  jobs. Jobs **don't coalesce** — take `pg_try_advisory_lock` at the start and exit "busy" if held.
  Non-idempotent delivery is its own job.
- **Per-instance state**: caches, single-flight locks and any per-process secret are per instance
  — design for N instances (see `console-backend` §4 for CSRF on autoscaled services).
- **Alerting**: alert on job failures, restart/crash counts and a dependency-probing health
  endpoint; verify the alert channel delivers.

## Translation: Docker / compose · Cloud Run · Azure Container Apps

| Concept | Your stack |
|---|---|
| Write ceiling | `read_only: true` + named volumes / `tmpfs` for each granted path; `cap_drop: [ALL]`; `security_opt: [no-new-privileges:true]` |
| Memory/log caps | `mem_limit`; logging driver `max-size`/`max-file`; Cloud Run memory limits + max instances |
| Secrets | Secret Manager / Key Vault references **pinned to a version** (not `latest`), mounted as env at runtime; rendered `.env` only for local dev |
| Timers | Cloud Scheduler → Cloud Run Jobs (explicit `--time-zone`); Container Apps jobs with cron triggers; idempotent jobs; a separate job for non-idempotent delivery |
| Alerting | Cloud Monitoring alert policies on job failures and restart counts; uptime checks that exercise the **function** (an endpoint that touches the DB), not just the container |
| Watchdog | a health endpoint that probes dependencies; alert on its result, not on container state |
| Provisioning | Terraform/Bicep: plan then apply; identity assertions as data sources; no `*` IAM grants |

## Checklist
- [ ] Every runtime write path granted, pre-created, and derived from code constants in a test.
- [ ] Per-tenant data scope enforced by the OS (drop-in / volumes), not just by the app.
- [ ] Secrets: version pinned, rendered via allowlist, 0640 root-owned, never printed, never hand-edited.
- [ ] Timers: explicit time zones, coalescing templated units, no started-by+After, non-idempotent delivery separate.
- [ ] One OnFailure template, stdlib notifier, keyed cooldowns, loud non-delivery.
- [ ] Watchdogs probe the function; memory and log ceilings installed; telemetry verified end to end.

Templates: [references/templates.md](references/templates.md).

## Related skills
`release-provenance` · `code-data-boundaries` · `multi-tenant-platform` · `console-backend`
