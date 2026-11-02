---
name: multi-tenant-platform
description: Serve many tenants (sites, clients, stores, departments) from one shared core without per-tenant complexity accreting. Covers the load-bearing question (does adding the second tenant make the third harder?), converge vs diverge, manifests as pure data plus a capped registry of named strategies, the rule of two, the simplicity ranking (canonical column > manifest constant > strategy > code), degenerate constants instead of optional fields, declared capabilities and semantics instead of probing, tenant as an explicit parameter resolved once, isolation in five layers, anchored scaffolding with a check mode, two onboarding milestones, and narrowing an engine by moving scoping to the caller. Use when designing SaaS, multi-site or multi-client systems, adding a tenant, reviewing code that branches on tenant identity, or when per-customer special cases creep into shared code.
---

# Multi-tenant platform: tenant N costs one adapter and one small manifest

> **The load-bearing question for every decision: does onboarding tenant #2 make tenant #3
> harder?** If yes, the design is wrong.


**On FastAPI · Postgres · Cloud Run:** tenant manifests as pydantic models with `extra="forbid"`; the tenant comes from the auth token via a dependency; Postgres RLS with `FORCE ROW LEVEL SECURITY` and a per-transaction `set_config`; one shared service for small tenants, a dedicated service + database for large ones. Translation table at the end.

## 1. Split by what must converge vs what should diverge

| Must **converge** (shared core, ships once) | Should **diverge** (per tenant, isolated) |
|---|---|
| engine and capability logic, the math | raw data and its quirks |
| the canonical contract + validator | vocabulary (how each spells a unit, a slot, a skill) |
| guardrails and security | schema mapping (the adapter) |
| the console and agent frameworks | which capabilities run; pace of adoption |

Adapters share **no code — only the output contract**, so tenant 3's weirdness is
quarantined in tenant 3's adapter. Complexity grows in the *adapter count* (linear,
isolated, cheap) while the engine converges (one fix helps every tenant).

Topologies considered: copy-paste repo per tenant (rejected — every fix is O(N) forever and
security fixes drift silently: "a guardrail fixed in 3 repos and missed in 97 is a breach";
AI lowers the cost of *writing* ports, not of verifying and reconciling them); a monorepo with
tenant as a parameter (a fine fallback); **thin tenant packs over a versioned shared core**
(the *intended* end state — co-located in one repo until the contract stabilizes, then split,
each tenant pinning a core version). In the reference system the split had not happened yet:
it ran as one repository whose deploy artifact is scoped per tenant, which already delivers
most of the isolation. Don't pay for packaging before the contract stops moving.

## 2. The manifest is data

Identity (`tenant_id`, display name), data root (by env var), `table_layout` (layout),
`datasets` (optional capabilities, each with an optional `fetch` declaration), strategy
picks from a **capped registry**, semantic flags, and validated policy knobs. Never freeform
code. A simple tenant's manifest is ~15 lines of degenerate defaults.

**Validate the manifest itself** (pydantic/JSON-Schema): reject unknown keys — a typo that
silently falls back to a default is a behaviour change nobody chose. Never let a reader
bypass the profile and parse the manifest on its own.

## 3. Strategies: named, capped, earned

- A **registry** `{name: implementation}`; `make(name, params)` raises on an unknown name; the
  tenant profile binds every strategy **once at load**.
- Strategies expose methods (`profile.normalize_unit(v)`, `profile.slots_for(date)`) —
  **never tenant ids**. `if tenant == "x"` in core is a blocker in review.
- **Rule of two**: no extension point until a *second* tenant needs the variance; until then,
  flatten it into the first tenant's adapter. Document any deliberate exception.
- A strategy names its own input field and raises if it is missing, rather than guessing.
- The registry should **shrink** over time; growth means variance is leaking out of data.

## 4. Push variance as far left as possible

> canonical column  >  manifest constant  >  named strategy  >  code

- **Materialize a column** (a classification flag the adapter computes) rather than a
  per-tenant function every consumer calls.
- **Degenerate constants, not optional fields**: make core *dimensions* required and let simple
  tenants emit constants (one slot, identity rotation, one zone). `for s in slots()` then
  works everywhere with zero branches. Scattered `if profile.has_x:` is the same disease as
  optionals. (Optional *datasets* are different and fine — behind one capability accessor, §5.)
- When an engine needs N tenant-specific rules, **narrow its job instead of widening its rule
  set**: move scoping to the caller (partition the problem — per zone, per floor — and call
  the unchanged engine once per scope, finest first, each pass seeing only what earlier
  passes left). Nesting the partition adds passes, not concepts. Know its costs:
  - **A finer first pass buys locality with fills** — later passes only see what is left idle,
    so measurably more slots go unfilled. Measure both numbers and let the tenant choose.
  - **Never split a cluster the plan binds together** (a person approved on several slots) across
    partitions, or one partition backfills a seat nobody left.
- **Tie-breaks are opportunistic**: never make an attribute only some tenants have (a grade) a
  required input; use the universal signal (e.g. a rating) as both filter and rank, and let
  optional metadata break ties where present.

## 5. Declared, not probed

- **Capabilities**: a tenant declares which optional datasets it provides; one accessor
  returns `(usable, fetched, message)`; a consumer that needs a missing one says so plainly
  and continues. Never infer capability from code shape (`hasattr(adapter, …)`) or from a
  file happening to exist (a header-only file once turned a set of decisions into "none").
- **Cross-check the declaration against reality** (recommended; designed, not built in the
  reference system): declared-but-absent → ERROR, present-but-undeclared → WARN. An empty
  fetch means "no data yet" and keeps the local data.
- **Semantics**: when tenants differ in what their data *means*, declare it — e.g.
  `attendance.records_absence` ("a missing row means absent" vs "unknown"),
  `presence.observes_location` ("this column can disagree with the plan" vs "it is copied
  from the roster"). Default to the common truth so existing tenants are untouched.
- **Prove a field can disagree before treating it as evidence**: a column copied from the
  roster can never contradict the roster; using it to veto a decision is a silent veto
  (it produced dozens of false "conflicts" on the tenant where it could not disagree).
- Caveat strings are **product output**, not logging.

## 6. Tenant is an explicit parameter, resolved once

- Every entry point takes `--tenant` (env var as default only), resolves the profile **once**,
  and passes it down. Store layout is always resolved through the profile
  (`profile.resolve_table_path(table, date=...)`), never hardcoded.
- A deployment declares `ENABLED_TENANTS`; the profile loader **raises** for any other id —
  rejected in code, not merely by prompt.
- `tenant_id` on every row from day one (ids collide across tenants); never join across tenants.

## 7. Isolation in independent layers

1. **Artifact**: only shared code + this tenant's pack ships; stale packs are removed.
2. **Config**: the env renderer copies only this tenant's secrets (others omitted, not blank)
   and filters admin/channel maps to in-scope tenants.
3. **OS sandbox**: this tenant's data root writable; every other known root inaccessible.
4. **Data-access gate**: the enabled-tenants check in the profile loader (or DB row-level security).
5. **Prompt/UI**: list only enabled tenants; ask which if ambiguous.

Plus per-tenant host, service identity, bucket, chat app and secret source. **Scope is a
property of the entrypoint** (`deploy/<tenant>.sh` fixes it and refuses an override), not a
flag someone can forget.

## 8. Onboarding: a scaffold, two milestones

- `scripts/scaffold_tenant.py <id>` (dry-run plan) → `--apply` → `--check`. It writes a
  manifest with degenerate defaults, a stub adapter that **exits loudly**, deploy/env/sandbox
  wiring — inserting at named anchors (`# TENANT-SCAFFOLD: <NAME>`) with **exactly-one-match**
  semantics, refusing to overwrite, and verifying itself. A hand-made deploy wrapper alone does nothing.
- **Milestone 1 — data/capability**: adapter + manifest; validator green; shared capabilities
  produce output; coverage gaps measured and handed to the tenant's domain expert (never
  hidden by fabricated fallbacks); acceptance tests added.
- **Milestone 2 — production**: isolated host/identity/bucket/chat app/secrets; restore once;
  health, validation, backup and capture timers observed live; parallel run before replacing
  an existing system. Never call a tenant "onboarded" after milestone 1 only.
- Enable **writes** for a tenant only when its rebuild provably replays human decisions —
  "the code carries no tenant branch" is a different claim from "safe to turn on".

## Translation: FastAPI · Postgres · LangGraph · Cloud Run

| Concept | Reference | Your stack |
|---|---|---|
| Manifest | `tenants/<id>/manifest.json` | `tenants` table or `tenants/<id>.yaml` validated by a pydantic `TenantManifest(extra="forbid")` |
| Resolve once | `profile = load(tenant)` at CLI entry | FastAPI dependency `get_profile(request) -> TenantProfile` (tenant from auth claims, never from the body) |
| Data-access gate | enabled-tenants check | Postgres RLS: `ENABLE` **and** `FORCE ROW LEVEL SECURITY` (owners bypass RLS otherwise); the app connects as a role without `BYPASSRLS`; policy `USING (tenant_id = current_setting('app.tenant_id', true))` (unset → no rows, not an error); set it per transaction with `set_config('app.tenant_id', $1, true)` — a session-level `SET` leaks across pooled connections |
| Strategies | `REGISTRY` dict | same; a `Protocol` per axis, classes registered by name |
| Isolation | host per tenant | shared Cloud Run service + RLS for low tiers; dedicated service/DB per tenant for high tiers — same code |
| Agent | prompt lists enabled tenants | tenant lives in server-side graph state / tool context; tools never accept a tenant id from the model |

## Checklist (reviewing a change)
- [ ] No branch on tenant identity in shared code; variance pushed left (column > constant > strategy).
- [ ] New strategy only if a second tenant needs it.
- [ ] New capability/semantic difference declared in the manifest with a common-truth default.
- [ ] Manifest schema updated; unknown keys rejected.
- [ ] Scaffold anchors updated if a new per-tenant integration point appeared; `--check` passes.

Templates: [references/templates.md](references/templates.md).

## Related skills
`canonical-data-pipeline` · `code-data-boundaries` · `hardened-runtime` · `legacy-port-migration` · `llm-agent-product`
