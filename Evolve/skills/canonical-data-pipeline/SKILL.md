---
name: canonical-data-pipeline
description: Turn messy per-source raw data into a validated canonical dataset every consumer can trust. Covers capture pipelines that keep raw bytes per (source, key, date), one idempotent adapter per source family, an executable data contract (required and optional columns, keys, grain, checks, ranges, ERROR vs WARN, additive-only versioning), atomic writes, lock-free staged rebuilds with a guarded install, content-keyed skip-unchanged, provenance markers, partitioning as a layout choice, defensive ingestion (parse by column name, identity fields fail hard, quarantine instead of guess), per-entity dropout guards, deterministic ordering, and validate-before-commit ingest of uploads. Use when building ETL or ingestion, defining a data contract or schema, integrating an external API or spreadsheet export, designing rebuilds or caches over derived data, or debugging numbers that look plausible but are wrong.
---

# Canonical data pipeline: raw → adapter → contract → consumers

> Adapters share no code — only the output contract. The weirdness of source N is
> quarantined in adapter N and cannot make source N+1 harder.

```
Capture   per-source fetchers, on schedule   → raw/<source>/<key>/<date>.*   (evidence: never edited)
Adapter   one idempotent program per source family → canonical tables          (the onboarding unit)
Contract  schema + keys + executable validator                                 (THE SEAM)
Consumers deterministic engines/skills read ONLY canonical + the manifest      (shared, converge)
Decisions human decision logs replayed over canonical on every rebuild         (see decision-ledger)
```


**On Postgres:** raw captures in object storage or append-only `raw_*` tables; each build writes its own table and a view swap installs it; ERROR checks as constraints plus set-based SQL (templates §11); a `build_runs` table for provenance; declarative partitioning by date.

## 1. Capture: data you didn't capture is gone

- Sources that only serve "now" (current shift, today's punches, live device state) must be
  **captured on a schedule**, or history is lost permanently. "A system you can serve is not
  a system you can keep."
- Keep raw **byte-faithful**, one file per `(source, key, date)`; take the date/slot from the
  capture path, not from parsing the content. Prefer a new file per capture over overwriting
  (an evidence store should not be mutable); report a capture that shrank.
- Distinguish `NOT_READY` from `ERROR`; run under a deadline; re-check that data actually
  landed — a fetch can "succeed" and land nothing.
- **Never substitute another date.** A request for a date the source can no longer serve is
  refused with a message, not answered with yesterday.
- Fetch an object **by name, never by "list and take newest"** when a look-alike addendum
  could appear (a partial addendum once looked like the newest full export).
- Fetch commands are **deploy config** (env vars); the tenant manifest only *declares* the
  capability (scope: `today_only | snapshot | today_growing | by_id`); the deployment
  decides whether it is live on this host.
- A second source for the same fact is unioned **at canonical**, with a per-row
  `data_source` column — never dropped into the first source's folder (a handful of rows placed
  in the wrong raw folder would have evicted hundreds).

## 2. Adapters: absorb the quirks so the output is boring

- One program per source family, idempotent, re-deriving only from raw files present.
  Running it never "downloads" anything — only declared fetchers touch the network.
- Parse **by column name**, case- and whitespace-insensitively; tolerate (and optionally
  capture) extra trailing columns. An upstream that re-cases a header or appends a column
  must not break ingestion.
- Expect: several tables in one sheet, duplicate headers (decide "first wins" explicitly
  and test it), changing filenames, dates in filenames that disagree with internal date
  fields (prefer the internal field).
- **Identity columns fail hard; everything else degrades loudly.** An optional column that
  vanished twice from an HR export failed the whole build twice — treat non-identity
  columns as "weather, not schema".
- **Count every skip.** "A blank cell in a discovery predicate is a delete statement"
  (a `continue` on blanks silently dropped real people).
- One bad input never takes down the tenant: per-file isolation + a rejection sidecar.
  Unknown sections land under a placeholder key with a warning instead of vanishing.
- **Quarantine instead of guess**: `*_unresolved.csv` with evidence. Never fuzzy-merge
  identities silently — a wrong merge is permanent and silent; send near-matches to a
  review queue with their score.
- Stamp the tenant id on every row **in one place** (the writer), and write every file
  atomically (§4).

## 3. The contract is code

Per table: `required`, `optional`, `keys` (non-null), `grain` (unique tuple, may include
nullable dimensions), `checks` (typed predicates), `ranges` (`(error_floor, warn_ceiling)`),
`optional_table`. Then:
- **ERROR blocks placement** (missing required column, null key, duplicate grain, below
  floor, unparseable); **WARN surfaces** (absent optional table, coverage < threshold,
  above soft ceiling).
- Versioned, **additive-only** (a removed/tightened column is a breaking change for every
  adapter); each column records the version that added it.
- Keys are **opaque strings** (`"7"`, `"B-2"`, `"GRP-K"` are all first-class); never cast.
- **Materialize a canonical column rather than adding a consumer function** (a
  classification flag as a column is diffable and visible; a function per tenant accretes).
- **Degenerate constants, not optional fields**: a dimension that is required everywhere
  (a single-shift tenant emits one constant shift) removes branches from every consumer.
- Validate the **staged** tree before install on **every** placement path (scheduled
  rebuilds included), quarantining on ERROR.
- Tenant #1 goes through the contract too, or the canonical schema silently *becomes* its raw
  schema (the half-canonical trap).

## 4. Writes and rebuilds without a big lock

- **Atomic write**: temp file in the *same directory*, dot-prefixed and uuid-suffixed (so
  globs never see it), fsync, `os.replace`, unlink on any exception. Readers see the whole
  old file or the whole new one — never a torn table.
- **Staged rebuild with a guarded install**:
  1. snapshot live hashes + the decision logs' revision **before** building;
  2. seed a staging sibling from live (adapters often read their own previous output — an
     empty staging dir is a *different* build, and one silently dropped real people);
  3. build with **no lock held**;
  4. diff staged vs seed (ignore marker-only restamps);
  5. take the lock, re-hash decisions + every file to be replaced; equal → `os.replace`
     each changed file; a removal only where live still equals the seed; moved → retry;
  6. bounded retries, then a blocking fallback for jobs that must land; report exactly
     which files landed on a partial install; an audit-write failure never fails the build.
- Never swap whole directories — files with different owners live there.
- Result in the reference system: lock hold went from tens of seconds per capture (most
  of a busy half-hour) to milliseconds.

## 5. Skip-unchanged and cache keys

- Key on the **content of everything the build can read**: raw tree, canonical minus run
  outputs, env-pointed files, env values, a digest of the code + runtime version, and —
  where "newest file wins" — each file's mtime **rank** in its directory.
- Record "nothing changed" only at an **observed fixpoint** (a guarded build that installed
  nothing with the key unchanged across the build) — a restore after a guarded build once
  produced a wrong skip.
- Read caches key on a **whole-store fingerprint** `(path, mtime_ns, size)` minus run-output
  dirs — a hand-written input list rots against the call graph. Enforce the read-set with
  an I/O-tracing test. Return immutable values or deep copies.

## 6. Provenance on derived data

A marker beside canonical (`_provenance.json`): tenant, fingerprint version, digest of the
adapter code (+ contract version), file count, `built_at`. `stamp()` runs **last** and
never raises; `check()` → `current | stale | unknown`, and a missing/corrupt marker is
**unknown, never current** (guess in the cautious direction). Exit 3 = "rebuild needed",
a warning, not a failed deploy. `built_at` changes only when content changes (otherwise
every cache downstream is invalidated every minute).

## 7. Partitioning is a layout choice, not a contract change

- Manifest `table_layout` map a table to `"<table>/{date}/slot-{slot}.csv"` or a flat file;
  columns, keys and grain are identical either way.
- `resolve_table_path(root, manifest, table, **fmt)` (usually bound to the tenant profile)
  **raises** if placeholders remain; `list_table_files(...)` enumerates deterministically in
  natural order; `partition_values(..., key)` returns `None` (not `[]`) for an
  unpartitioned table. A partitioned table read as flat returns zero rows — which looks
  like a quiet day.
- Partition on the grain readers ask for (a one-day question that parsed the whole
  history became ~30× cheaper after partitioning).
- **Migrate the data before the code that reads it**; keep superseded flat files (named in
  the manifest as frozen) and stop reading them.

## 8. Guards that report, never repair

- **Dropout audit** for reference-data refreshes: persist the previous snapshot's key set,
  diff **per entity** (totals can improve while people vanish), attach **independent**
  liveness evidence (activity logs), write a named report, warn, keep ingesting.
- Every merge returns the rows it refused, not just a message.
- **Write the cross-source policy down as data**: when two sources describe the same field
  (a roster and a presence feed both carry a role), keep a per-field table of which source wins,
  at what severity a disagreement is reported, and the measured disagreement rate. A reviewer
  checks the table before calling a precedence "a bug".
- **Totals cannot see per-key loss** — compare key by key.

## 9. Deterministic total order

`sorted(values, key=str.casefold)` is not deterministic (ties keep hash order across
processes; under a row cap that changes *who is visible*). End every sort key with the raw
value: `(v.casefold(), v)`; natural sort with numeric runs; **one sort key per concept**,
shared by server and client and proven equal by a parity test; prove determinism by
running under several `PYTHONHASHSEED`s with a control that shows the naive key varies.

## 10. Uploaded files: validate before commit

stage the raw corpus + the new file → run the adapter into staging → validate → **only then**
place the raw file permanently and swap canonical files one by one (with backup); dedupe on
`(tenant, intent, sha256)`; share the tenant write lock with every other writer; audit every
outcome including executor exceptions. (A rejected upload left in the live raw folder once
won the next rebuild's newest-file glob.)

## Translation: Postgres · pydantic · object storage · dbt

| Concept | Reference stack | Your stack |
|---|---|---|
| Raw store | files per (source, key, date) | object storage keys `raw/<source>/<key>/<date>/<captured_at>.json` or append-only `raw_*` tables with `captured_at` |
| Adapter | Python program → CSVs | Python job / dbt models → `canonical.*` tables |
| Contract | `schema.py` + validator | pydantic models for rows + DB constraints (`NOT NULL` keys, `UNIQUE` grain, `CHECK` ranges) for ERROR; pandera/Great Expectations for WARN-level coverage |
| Atomic swap | temp + `os.replace` | build into a staging schema, validate, then swap in one transaction (`ALTER TABLE … RENAME`) or `CREATE OR REPLACE VIEW` |
| Guarded install | lock + re-hash | `pg_advisory_xact_lock(tenant_key)` + compare input-version rows before swapping |
| Provenance | `_provenance.json` | `build_runs(id, code_sha, contract_version, inputs_digest, built_at)`; canonical rows carry `build_run_id` |
| Partitioning | path templates | declarative partitioning by date; queries always bound the partition key |
| Dropout guard | per-entity diff + activity evidence | `SELECT id FROM prev EXCEPT SELECT id FROM curr` joined to recent activity events |

## Checklist
- [ ] Ephemeral sources captured on schedule; raw is evidence (append, not overwrite).
- [ ] Adapter parses by name, fails hard only on identity, counts skips, quarantines guesses.
- [ ] Contract declared in code; ERROR blocks placement on every path; additive versioning.
- [ ] All writes atomic; rebuild staged, baseline before build, lock only to install.
- [ ] Skip/cache keys cover the full readable closure; read-set enforced by a test.
- [ ] Provenance marker; unknown ≠ current.
- [ ] Dropout audits per entity with independent evidence; sorts total and shared.

Templates: [references/templates.md](references/templates.md).

## Related skills
`multi-tenant-platform` · `decision-ledger` · `safe-writes` · `code-data-boundaries` · `test-gates` · `synthetic-world`
