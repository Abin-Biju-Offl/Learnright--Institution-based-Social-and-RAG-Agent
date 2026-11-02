---
name: legacy-port-migration
description: Migrate a working legacy system (single-customer scripts, an old service, a notebook prototype, a vendor tool) into a new architecture without breaking its users. Covers shaping the contract from two real datasets, carving the seam under byte-identity or parity tests, porting the least-coupled capability first and the foundational one second, categorising every break on the second customer (that list is the interface spec), a near-identity adapter so there is one implementation, hermetic comparisons, accepting deliberate divergences as reported invariants, parallel runs on real traffic, and retiring the equivalence proof from the gate after lifting its invariants. Use when porting legacy code, rewriting a module, generalising a single-customer system into a platform, replacing a tool, or deciding when a parity test should stop gating releases.
---

# Legacy port migration: carve the seam under evidence

> Run the old tools against the second customer and they rarely crash — they **silently
> misbehave**: an opaque key like `"B-2"` normalised to the integer 2, a slot name mapped onto
> the first customer's codes. Silent misbehaviour is the expensive failure mode, and only
> evidence catches it.

## 1. Shape the contract from two data points

Hand-build the second customer's canonical data with throwaway-but-idempotent scripts, then run
the **least-coupled** capability on it first to *discover* what the contract must absorb.
"Designing a superset from one data point and validating it against the second is worse than
discovering it from two."

## 2. Carve the seam under equivalence protection

1. Extract the first customer's vocabulary out of the engine **as data** (a manifest), with the
   engine delegating to it.
2. Write the contract as an **executable validator** (see `canonical-data-pipeline`).
3. Prove non-regression: a shim/parity test showing the original customer's outputs are
   **byte-identical** through the new seam.
4. Pass an external **design review gate** before freezing the seam; log the must-fix list and
   close it before proceeding.

## 3. Port in dependency order

| Order | Capability | Why |
|---|---|---|
| 1 | the least-coupled one (pure math, no time/team/presence coupling) | the clean smoke test: "is the engine portable at all?" |
| 2 | the **foundational generator** (whose output others consume) | it stresses the most primitives; everything downstream depends on it |
| … | medium coupling | validates the shared model on the new data |
| last | the one with the most customer-specific "sociology" | running it early just cascades the earlier breaks |

## 4. Categorise every break — the list is the interface spec

Run every capability on customer #2 and file each failure as:
- **(a) adapter/data** — fix in that customer's adapter;
- **(b) a missing manifest value** — add a declared value/strategy;
- **(c) a customer-#1-ism hiding in core** — promote it to a capability at the interface.

That categorised list *is* the interface specification. Then **reorder by value**: if the second
customer's key data barely resolves (only a small fraction of its operations mapped to skills),
fix that before porting more. A design review once found the architecture sound but the
roadmap drifting from *improving outcomes* toward *proving portability* — portability is the
means, not the end.

## 5. One implementation

Give the original customer a **near-identity adapter** so it runs the same core as everyone —
kill the transitional forks. "Done porting" = byte-identical on customer #1 **and** end-to-end on
customer #2, per capability.

## 6. Equivalence tests that mean something

- **Hermetic**: if the legacy side calls a live API at run time, its output moves *by the day*,
  not by the code — neutralise the network for the whole process tree (a dead proxy) or serve both
  sides one pinned fixture.
- Compare **modulo columns the new system adds deliberately**, excluded explicitly by name.
- Distinguish "we're behind upstream" (red = the signal to **pull**, never to re-baseline) from
  "we deliberately differ" (exclude or accept, recorded).

## 7. Deliberate divergence: from identity to invariants

When the new system *intentionally* changes behaviour, stop asserting byte identity:
- assert the **invariants** (row identity, the shared values that must not move);
- **report — never fail on — accepted divergences**, each traced to a named root cause and proven
  record by record, with counts per column so an anomaly stays visible (a figure that matched a
  documented ÷8 conversion on all rows but one was flagged loudly, not waved through);
- then **break the code on purpose** to prove the relaxed test still catches regressions — "an
  allowance nobody has tried to break is a waiver with better wording".

## 8. Parallel run before cut-over

Run real requests against old and new side by side and diff before replacing a live system.
Keep the old one runnable until the new one has matched it on real traffic.

## 9. Retire the proof (don't delete it)

Once live, the release gate asks **"does what works today still work?"**, not "did the port match
the legacy system". Retiring follows `test-gates` §10: classify each assertion, lift invariants
into fast tests, list the paths left unguarded in a tracked issue, keep the proof runnable in an
archived suite, and never put it back in front of a release to cover a gap. (In the reference
system, migration proofs were most of the gate's runtime; retiring them cut it by more than half.)

## Translation: notebook → service, Python → TS, DB migrations

| Situation | Apply it as |
|---|---|
| Notebook prototype → FastAPI service | freeze a fixture dataset; the notebook's outputs are the oracle; parity tests per endpoint; then invariants + behaviour tests; archive the notebook comparison |
| Server logic ported to the browser (TS) | shared JSON fixtures, pytest + vitest parity tests, figure by figure |
| Schema/storage migration | migrate data first (idempotent, add-only), dual-read and diff per record, cut readers over, keep the old store frozen (named) |
| Replacing a vendor tool | parallel run on real inputs; categorise each difference (theirs wrong / ours wrong / deliberate) |

## Checklist
- [ ] Contract shaped from two real datasets; seam carved with a byte-identity proof on #1.
- [ ] Ports in coupling order; every break categorised (a)/(b)/(c).
- [ ] Equivalence tests hermetic; deliberate additions excluded by name; divergences reported with counts.
- [ ] Parallel run before cut-over; proof archived (not deleted) after invariants are lifted.

Templates: [references/templates.md](references/templates.md).

## Related skills
`test-gates` · `multi-tenant-platform` · `canonical-data-pipeline` · `engineering-journal`
