---
name: architecture-bootstrap
description: Start, or retrofit, a project with this architecture DNA in the right order. A step-by-step playbook that lays down the repository skeleton and its boundaries, the documentation system, the coding-agent rules file, the test runner with suites and a release gate, CI, a synthetic world, the data contract and pipeline, the decision ledger, the write protocol, the backend and touch UI system, decision authority and detectors, the LLM agent layer, release provenance and the hardened runtime — with adoption tiers (what to add on day one vs at scale), a skeleton for a FastAPI + React + Postgres + LangGraph/MCP + Docker + GitHub Actions + Cloud Run stack, and which skill to load at each step. Use when creating a new repository, kicking off a portfolio or client project, retrofitting discipline onto an existing codebase, or asking "where do I start with all of this?"
---

# Architecture bootstrap: adopt the DNA in order

Read [references/ARCHITECTURE-DNA.md](references/ARCHITECTURE-DNA.md) once for the whole
picture (it is a copy of the kit's root document, so this skill works when installed on its
own). This skill is the **order of operations**. Rule 0 applies to the DNA itself: **adopt a mechanism when you can name the
problem it removes** — the incident class has appeared, or is clearly imminent. Don't build
tier 2 on day one.

## The five mental models (keep these in your head)

1. **Two truths** — code's truth is version control and ships as an artifact; data's truth is
   the running system and flows up to backup only.
2. **Product vs workbench** — what production needs at 3am vs what only builders need.
3. **Converge vs diverge** — one shared core behind an executable contract; per-tenant variance
   pushed into adapters and manifest data.
4. **Humans decide; software informs** — the most specific human decision wins; suggestions are
   not decisions; nothing captured is ever deleted.
5. **Evidence over prose** — a claim is verified when you've seen it fail; facts that can run
   become tests or registries; prose records *why*.

## Adoption tiers

| Tier | When | Adopt | Skills |
|---|---|---|---|
| **0 — day one** | any repo | layout + lockstep ignore/exclude lists; rules file + docs map + journal/status; test runner, suite registry, fails-at-base script, CI fast suite; atomic writes | `code-data-boundaries`, `engineering-journal`, `agentic-workbench` §1–3, `test-gates` |
| **1 — first real users** | people enter data / decisions | data contract + validator; decision ledger (never delete); safe-write protocol + typed refusals; release line + provenance manifest; hardened runtime basics; startup banner | `canonical-data-pipeline`, `decision-ledger`, `safe-writes`, `release-provenance`, `hardened-runtime`, `console-backend` |
| **2 — scale** | tenant #2, many concurrent users, many contributors/agents | manifests + strategies + scaffold; per-tenant isolation; readiness board; version-keyed caches + read budgets; fleet reader; reviewer agent + hard rules; UI tokens, registry and backlog-as-code | `multi-tenant-platform`, `readiness-detectors`, `console-backend` §5–8, `agentic-workbench` §4–8, `touch-ui-system` |
| **3 — AI product** | an LLM talks to users | declared context, deterministic tools (MCP), layered guardrails, writes outside the loop, traces, evals | `llm-agent-product`, `human-decision-authority`, `test-gates` templates §13 |

Porting an existing system? Load `legacy-port-migration` before tier 2.
No real data allowed? Load `synthetic-world` before tier 1.

## Step-by-step

**Step 1 — Layout and boundaries** (`code-data-boundaries`)
Repo holds code + workbench; data lives in a sibling data root (or the database). Write
`.gitignore`, `.dockerignore`/deploy-exclude list with a workbench block, and
`tests/test_lockstep.py`. *Done when* the transfer dry-run test passes.

**Step 2 — Documentation and rules** (`engineering-journal`, `agentic-workbench`)
`README.md` (docs map + Status/Next), `SPEC.md`, `design.md`, `LOG.md`, `CLAUDE.md` +
`AGENTS.md`, `docs/decision-authority.md` (even a stub), `.claude/review/hard-rules.md` with
rules 0, 0b, 1–3. *Done when* a new agent session can answer "what is this, why, and what must I
never do" from the files alone.

**Step 3 — Tests and the gate** (`test-gates`)
`scripts/suites.py` (fail closed), `scripts/run_suite.py` (failed / setup / killed),
`scripts/run_gate.sh`, `scripts/prove-fails-at-base.sh` (+ its self-test),
`tests/offline_env.py`, `tests/test_suite_boundaries.py`, CI running the fast suite on every PR.
*Done when* CI is green and the base-check self-test proves a failing case.

**Step 4 — Data** (`synthetic-world`, `canonical-data-pipeline`, `multi-tenant-platform`)
Blueprint + seeded generator → adapter → contract + validator → canonical tables; provenance
marker; manifest even for one tenant (degenerate defaults). *Done when* the validator is green on
the generated world and regeneration is byte-identical.

**Step 5 — Decisions and writes** (`decision-ledger`, `safe-writes`)
Append-only decision tables with one `in_force` view; tenant lock / advisory lock; scoped
preconditions; typed refusals; audit. *Done when* "turn it off" and "undo" are rows, and a test
proves a refused save keeps the user's edits.

**Step 6 — Backend and UI** (`console-backend`, `touch-ui-system`)
One write gate before dispatch; per-request identity; error map; startup banner. UI: closed token
scale, base-selector floors, static gates, registry, one feedback path, transport-level busy.
*Done when* the UI gates run in CI and Playwright confirms no horizontal scroll at 360px.

**Step 7 — Authority and detectors** (`human-decision-authority`, `readiness-detectors`)
Write the authority stack for your domain; build the first detectors with the issue model and the
severity function. *Done when* no detector flags a human-chosen difference and every issue has an
action or an owner.

**Step 8 — The LLM agent** (`llm-agent-product`)
MCP server with typed read-only tools (tenant injected server-side); generated system prompt;
provider registry; deny function + redaction; writes behind a human gate; traces; evals as the
acceptance suite. *Done when* evals assert tools and values, and a test proves the agent discovers
nothing from the filesystem.

**Step 9 — Release and runtime** (`release-provenance`, `hardened-runtime`)
Image built from the commit on main; deploy job needs the gate; provenance labels; per-target
approval; fleet reader; read-only container FS, pinned secrets, alerting, ceilings. *Done when* the
fleet reader shows every target `current` and live.

**Step 10 — Workbench automation** (`agentic-workbench`)
PR-reviewer agent + orchestrator; ops skills that are runbooks; prose resolver in review.

## Skeleton for FastAPI · React/TS · Postgres/pgvector · LangGraph + MCP · Docker · GitHub Actions · Cloud Run

```
your-app/
├── CLAUDE.md  AGENTS.md  README.md  SPEC.md  design.md  LOG.md      # workbench (never in the image)
├── docs/decision-authority.md  docs/adr/                            # workbench
├── .claude/review/hard-rules.md  .claude/agents/pr-reviewer.md      # workbench
├── backend/app/
│   ├── main.py              # routers; write router behind Depends(require_write)
│   ├── auth.py              # per-request identity, CSRF, admin allowlist
│   ├── errors.py            # typed refusals → status + code (one table)
│   ├── safe_write.py        # advisory lock, scoped preconditions, audit
│   ├── decisions.py         # append-only decision ledger + in_force view
│   ├── contract/            # pydantic row models + validator (ERROR/WARN)
│   ├── tenants/             # manifest models (extra="forbid") + strategy registry
│   ├── services/            # deterministic engines (forecast, optimizer, …): pure + tested
│   ├── readiness/           # detectors + severity function
│   ├── agent/               # prompt builder, provider registry, blocked_reason, redaction, traces
│   └── reports/             # PDF/Excel rendered from SAVED state
├── mcp_server/              # typed read-only tools; tenant from server-side context
├── frontend/src/
│   ├── ui/tokens.css  ui/registry.ts  ui/backlog.ts   # closed scales, enforced catalogue
│   └── lib/apiFetch.ts      # one fetch: busy tracking, re-auth, conflict replay
├── world/                   # blueprint + seeded generator + _pack.json  (synthetic-world)
├── evals/cases.yaml         # scenario ids, expected tools and values
├── scripts/                 # suites.py run_suite.py run_gate.sh prove-fails-at-base.sh check_prose_refs.py fleet_check.py
├── tests/                   # fast (default) + acceptance (registered) + archived
├── deploy/RUNBOOK.md        # ships: the operator's document
├── .gitignore  .dockerignore                # lockstep for data/secrets; workbench excluded from the image
├── docker-compose.yml       # read_only, volumes, seed job, healthchecks
└── .github/workflows/       # ci.yml (fast on PR) · release.yml (gate → image by digest → per-env approval)
```

## Retrofitting an existing codebase (in this order)

1. **Honest gate signals** (failed vs killed vs setup) and the **fails-at-base** script — every
   later change needs trustworthy evidence.
2. **Docs map + journal + status discipline** — so knowledge stops evaporating.
3. **Boundaries**: lockstep ignore/exclude lists, workbench out of the artifact.
4. **Atomic writes + never-delete** — before the first data-loss incident, not after.
5. **Release line + provenance** — "what is running where?" answerable in one command.
6. **UI token scale + base floors + registry** — before the third copy of any control.
7. **Tenant seams** — when tenant #2 is real, not before.

## Related skills
All of them — this is the index in execution order.
