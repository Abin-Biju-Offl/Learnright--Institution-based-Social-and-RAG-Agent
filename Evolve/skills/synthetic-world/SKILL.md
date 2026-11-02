---
name: synthetic-world
description: Generate a realistic, reproducible synthetic dataset — "a declared world, not a measured one" — for demos, tests, onboarding and portfolio projects. Covers a blueprint that declares the world, a seeded deterministic generator (byte-identical regeneration), export through the same adapter and data contract as real data, a provenance file recording blueprint, seed, run id and exactly which tables are generated vs seeded, deliberate realistic messiness that exercises the pipeline's defences, explicit absence semantics, zero-config discovery, named scenarios shared by tests, demos and evals, size tiers, and the rules for keeping it free of real names and data. Use when a project must not use real data (privacy, IP, portfolio rules), when building fixtures or a demo tenant, when onboarding needs a sample dataset, or when tests need a seeded world that behaves like production.
---

# Synthetic world: declared, seeded, reproducible

> "This is a declared world, not a measured one" — say so in the data itself, record exactly
> what was generated, and make regeneration byte-identical so the folder diffs clean.

## 1. Why a world, not a handful of fixtures

- Real data is often off-limits (privacy, IP, a portfolio rule of "synthetic or public only").
- Tiny hand-written fixtures can't express the bugs that matter: a fixture must differ from
  production **on the dimension under test** (single-slot, single-tenant fixtures hide whole
  classes of bugs).
- Demos, evals and onboarding all need one coherent world that exercises every path.

## 2. Blueprint → generator → canonical pack

1. **Blueprint** (YAML/JSON): sizes, entity types, distributions, calendars and rules — units,
   people, skill/rating distributions, attendance *rates*, rotation calendar, layouts per variant,
   plan horizon, named anomalies to inject.
2. **Generator**: a seeded RNG **per entity stream** (so adding one person doesn't reshuffle every
   other value), no wall clock (dates derive from a `seed_date`), total sort orders, stable ids.
   Same blueprint + seed → **byte-identical** output.
3. **Export through the real adapter → canonical tables** (the same contract real tenants use);
   run the validator; the pack is just another tenant.

## 3. Provenance travels with the pack

`_pack.json` beside the data:
```json
{
  "blueprint": "small-site@3", "generator_version": "1.4.0", "code_digest": "sha256:…",
  "run_id": "run_9c1f…", "rng_seed": 7, "seed_date": "2026-03-13",
  "declared_world": true,
  "tables": {
    "people":     {"origin": "seeded",    "rows": 1200},
    "layouts":    {"origin": "seeded",    "rows": 260},
    "attendance": {"origin": "generated", "rows": 6400,
                   "note": "drawn per (seed, date, person) from each person's attendance rate"}
  },
  "anomalies": ["duplicate_header:ratings", "id_change:person-0412", "absent_sundays"],
  "absence_semantics": "absent means missing: a person who did not attend has no row"
}
```
Readers and README state the **absence semantics** explicitly, and the pack says which tables it
does *not* include (and that readers degrade quietly when they are missing).

## 4. Messiness on purpose

Inject the problems the pipeline must survive, each toggled in the blueprint and listed in
provenance: re-cased and duplicate headers, an extra trailing column, a missing optional table,
an unknown code, a person with no rating, two people with the same name, an id change (alias),
someone dropped from a reference snapshot while still active, a partial "addendum" export, a
renumbered layout, a rotation flip week, a holiday with no data. A clean world tests nothing.

## 5. Scenarios: one library for tests, demos and evals

Name scenarios (`two_absent_on_unit_1`, `new_variant_starts_monday`, `renumbered_layout`,
`identity_changed_overnight`) with **the expected outcome written down** ("throughput drops by
less than 15% vs the naive plan"; "the assistant cites the correct procedure"). The same ids
appear in fast tests, acceptance tests, LLM eval cases and the manual demo checklist.

## 6. Zero-config discovery

Default to a sibling directory next to the repo (`../<app>-data/`), override with one env var.
README: "Install — pick one: A. drop the folder beside the repo (zero config) · B. put it anywhere
and set `APP_DATA_ROOT`."

## 7. Determinism is tested

- Generate twice → identical file hashes; generate under two `PYTHONHASHSEED`s and two time zones
  → identical.
- Golden **scoped** counts as acceptance fixtures ("1,200 people, 18 running units, 7 days;
  Sunday absent").
- Bump `generator_version` when output changes on purpose; record why in the journal.

## 8. Size tiers

| Tier | Use | Budget |
|---|---|---|
| tiny | fast-suite fixtures | runs in < 1 s, committed |
| demo | onboarding, screenshots, evals | a few MB, generated in CI or committed as a pack |
| large | performance and partitioning tests (work-count budgets) | generated on demand, never committed |

## 9. Keep it clean

No real person, company, client or product names (use neutral generated names and a fictional
organisation), no copied documents (write procedures yourself or use openly licensed text), no
secrets (placeholders in `.env.example`). The repo states this rule at the top of its README.

## Translation: Python · Postgres · pgvector · compose

| Concept | Your stack |
|---|---|
| Seeded streams | `numpy.random.Generator(PCG64(seed))` spawned per entity (`SeedSequence.spawn`), or `random.Random(f"{seed}:{entity}")`; `Faker.seed_instance(seed)` for names |
| Load | write canonical CSVs, then `COPY` into Postgres in a compose init job that runs once on an empty volume |
| RAG documents | self-written procedures; embeddings computed at build time; record the embedding model + version in `_pack.json` |
| Evals | eval cases reference scenario ids; expected tools and values computed from the world |

Templates: [references/templates.md](references/templates.md).

## Related skills
`canonical-data-pipeline` · `test-gates` · `multi-tenant-platform` · `llm-agent-product`
