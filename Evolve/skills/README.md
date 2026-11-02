# Architecture DNA — skills

Eighteen Claude Code skills, distilled from a production multi-tenant, AI-assisted
operations platform. They are domain-neutral and stack-aware, and every template is written
fresh. The whole picture lives in [`../ARCHITECTURE-DNA.md`](../ARCHITECTURE-DNA.md);
these skills are the executable detail.

## Install

Each skill is a folder containing `SKILL.md` (frontmatter `name` and `description`, then
the body) and an optional `references/` folder.

Install them for **one project**, so the skills travel with the repo:
```bash
PROJECT=~/code/my-app            # your project
SKILL=test-gates                 # the skill to install
mkdir -p "$PROJECT/.claude/skills"
cp -r "skills/$SKILL" "$PROJECT/.claude/skills/"
```

Or install them for **every project** on this machine:
```bash
mkdir -p ~/.claude/skills
cp -r skills/*/ ~/.claude/skills/
```
On Windows the user folder is `%USERPROFILE%\.claude\skills\`.

Claude Code chooses a skill from its `description`. You can also invoke one by name, for
example `/test-gates`.

For Codex, Cursor or human readers, the files are plain Markdown. Point `AGENTS.md` or a
rules file at the skills you want followed.

Pick the skills you need rather than installing all eighteen. A small project usually starts
with `architecture-bootstrap`, `code-data-boundaries`, `test-gates`, `engineering-journal`
and `agentic-workbench`.

## Index (in adoption order)

| # | Skill | Category | Tier |
|---|---|---|---|
| 1 | [`architecture-bootstrap`](architecture-bootstrap/SKILL.md) | Orchestration: what to adopt, in what order | — |
| 2 | [`code-data-boundaries`](code-data-boundaries/SKILL.md) | Repo layout, two truths, product vs workbench | 0 |
| 3 | [`engineering-journal`](engineering-journal/SKILL.md) | Docs system, journal, status, decision records | 0 |
| 4 | [`test-gates`](test-gates/SKILL.md) | Suites, registry, fails-at-base, hermetic tests, static gates | 0 |
| 5 | [`agentic-workbench`](agentic-workbench/SKILL.md) | Agent rules, hard rules, reviewer agent, worktrees, ops agents | 0–2 |
| 6 | [`synthetic-world`](synthetic-world/SKILL.md) | Seeded, declared datasets for tests, demos and evals | 1 |
| 7 | [`canonical-data-pipeline`](canonical-data-pipeline/SKILL.md) | Capture, adapters, executable contract, staged rebuilds | 1 |
| 8 | [`decision-ledger`](decision-ledger/SKILL.md) | Never delete; append-only decisions; identity vs presence | 1 |
| 9 | [`safe-writes`](safe-writes/SKILL.md) | Locks, install guard, scoped preconditions, refusals | 1 |
| 10 | [`console-backend`](console-backend/SKILL.md) | Minimal robust web backend | 1–2 |
| 11 | [`release-provenance`](release-provenance/SKILL.md) | Release line, artifacts, provenance, fleet reader | 1 |
| 12 | [`hardened-runtime`](hardened-runtime/SKILL.md) | Sandboxed services, secrets, timers, alerting, watchdogs | 1 |
| 13 | [`multi-tenant-platform`](multi-tenant-platform/SKILL.md) | Manifests, strategies, isolation, scaffolding | 2 |
| 14 | [`touch-ui-system`](touch-ui-system/SKILL.md) | Tokens, floors, registry, backlog-as-code, UI gates | 2 |
| 15 | [`human-decision-authority`](human-decision-authority/SKILL.md) | Authority stack, detectors, suggestions, advisory engines | 2–3 |
| 16 | [`readiness-detectors`](readiness-detectors/SKILL.md) | Actionable issue boards | 2 |
| 17 | [`llm-agent-product`](llm-agent-product/SKILL.md) | Safe, honest LLM agent products | 3 |
| 18 | [`legacy-port-migration`](legacy-port-migration/SKILL.md) | Porting a legacy system under evidence | as needed |

## How they connect

```
architecture-bootstrap ──► code-data-boundaries ──► release-provenance ──► hardened-runtime
        │                         │
        ├──► engineering-journal ◄┼── agentic-workbench ──► test-gates ◄── legacy-port-migration
        │                         │
        └──► synthetic-world ──► canonical-data-pipeline ──► multi-tenant-platform
                                      │
                    decision-ledger ◄─┴─► safe-writes ──► console-backend ──► touch-ui-system
                          │
       human-decision-authority ──► readiness-detectors
                          │
                   llm-agent-product
```

## Conventions inside each skill

Each skill follows the same layout:

- **Principles first**, each with the failure that motivated it, retold generically.
- **Recipes and checklists** you can act on.
- **Templates** in `references/` (usually `templates.md`; `agentic-workbench` splits them into
  three files, and `architecture-bootstrap` carries a copy of the master document). The reference
  stack is Python, Bash, systemd and vanilla JS.
- A **translation table** for FastAPI, React/TS/Vite/Tailwind, Postgres/pgvector,
  LangGraph + MCP, Docker, GitHub Actions and Cloud Run or Azure Container Apps.
- **Related skills**, linked at the end.

## Provenance and limits

- **What the kit contains.** Concepts and practices generalized from a real system, with no
  employer, client or product names and no real data. Code templates are illustrative and
  freshly written.
- **Before using templates in production,** adapt them to your stack, run their tests, and
  check SDK and API details against current documentation.
- **Template versions.** Model IDs and SDK option names in the LLM templates were current as
  of 2026-10.
