# canonical-data-pipeline — templates

Dependency-free Python (stdlib `csv`); swap in pandas/polars freely.

## §1 Contract declaration

```python
# contract/schema.py — the validator IS the spec. Additive-only; note the version per column.
SCHEMA_VERSION = "1.2.0"


def nonempty(v: str) -> bool:
    return bool(str(v).strip())


def intlike(v: str) -> bool:
    try:
        return float(v) == int(float(v))
    except ValueError:
        return False


TABLES: dict[str, dict] = {
    "people": {
        "required": ["tenant_id", "person_id", "name", "home_unit"],
        "optional": ["grade"],                                   # 1.1.0
        "keys": ["tenant_id", "person_id"],                      # non-null
        "grain": ["tenant_id", "person_id"],                     # unique tuple
        "checks": {"person_id": nonempty},
    },
    "ratings": {
        "required": ["tenant_id", "person_id", "skill", "pct"],
        "optional": ["variant", "status"],                       # status: 1.2.0 (WITHDRAWN keeps the row)
        "keys": ["tenant_id", "person_id", "skill"],
        "grain": ["tenant_id", "person_id", "skill", "variant"], # nullable dimension in the grain
        "ranges": {"pct": (0, 200)},                             # < 0 ERROR, > 200 WARN
    },
    "sensor_readings": {
        "required": ["tenant_id", "unit", "ts", "value"],
        "keys": ["tenant_id", "unit", "ts"],
        "grain": ["tenant_id", "unit", "ts"],
        "optional_table": True,                                  # absent = WARN; consumers degrade
    },
}
```

## §2 Validator (ERROR blocks placement, WARN surfaces)

```python
#!/usr/bin/env python3
"""contract/validate.py <canonical-root> [--file table=path ...]   exit 1 on any ERROR.
For a partitioned table, validate each partition (`--file table=<path>`, or loop over
list_table_files() from §4) — otherwise the flat path is reported missing."""
import argparse, csv, sys
from pathlib import Path
from schema import TABLES

MAX_PER_TABLE = 20


def validate(name: str, spec: dict, path: Path) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    if not path.exists():
        (warns if spec.get("optional_table") else errors).append(f"{name}: table missing ({path})")
        return errors, warns
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        dupes = sorted({c for c in header if header.count(c) > 1})
        if dupes:
            errors.append(f"{name}: duplicate header(s) {dupes} — a dict reader silently keeps only the last")
        missing = [c for c in spec["required"] if c not in header]
        if missing:
            return errors + [f"{name}: missing required column(s) {missing}"], warns
        seen, rows = set(), 0
        for line, row in enumerate(reader, start=2):
            rows += 1
            for k in spec["keys"]:
                if not (row.get(k) or "").strip():
                    errors.append(f"{name}:{line}: null key {k}")
            grain = tuple((row.get(c) or "").strip() for c in spec["grain"])
            if grain in seen:
                errors.append(f"{name}:{line}: duplicate grain {grain}")
            seen.add(grain)
            for col, ok in spec.get("checks", {}).items():
                v = row.get(col)
                if v not in (None, "") and not ok(v):
                    errors.append(f"{name}:{line}: {col}={v!r} fails {ok.__name__}")
            for col, (floor, ceiling) in spec.get("ranges", {}).items():
                v = (row.get(col) or "").strip()
                if not v:
                    continue
                try:
                    x = float(v)
                except ValueError:
                    errors.append(f"{name}:{line}: {col}={v!r} is not a number")
                    continue
                if floor is not None and x < floor:
                    errors.append(f"{name}:{line}: {col}={x} below {floor}")
                elif ceiling is not None and x > ceiling:
                    warns.append(f"{name}:{line}: {col}={x} above {ceiling}")
        if rows == 0:
            warns.append(f"{name}: no rows")
    return errors, warns                     # full lists: the caller counts all, prints a few


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--file", action="append", default=[], help="table=path (one partition)")
    args = ap.parse_args()
    overrides = dict(item.split("=", 1) for item in args.file)
    total_errors = 0
    for name, spec in TABLES.items():
        path = Path(overrides.get(name, args.root / f"{name}.csv"))
        errors, warns = validate(name, spec, path)
        for e in errors[:MAX_PER_TABLE]:
            print("ERROR", e)
        for w in warns[:MAX_PER_TABLE]:
            print("WARN ", w)
        if len(errors) > MAX_PER_TABLE:
            print(f"ERROR {name}: … and {len(errors) - MAX_PER_TABLE} more")
        total_errors += len(errors)          # the exit code and the count see EVERY error
    print(f"{total_errors} error(s)")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

## §3 Atomic write

```python
import os, uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_write(path, *, encoding="utf-8", newline=""):
    """Content appears at `path` only once complete. Same directory on purpose:
    os.replace is atomic only within one filesystem. Dot-prefixed so `*.csv` globs never
    see a partial file; uuid-suffixed so two writers never collide."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex[:12]}")
    try:
        with tmp.open("w", encoding=encoding, newline=newline) as fh:
            yield fh
            fh.flush()
            os.fsync(fh.fileno())          # durability: no present-but-empty file after power loss
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
```

## §4 Layout-agnostic table resolution

```python
import re
from pathlib import Path


class LayoutError(ValueError):
    pass


def _template(manifest: dict, table: str) -> str:
    return (manifest.get("table_layout") or {}).get(table, f"{table}.csv")


def resolve_table_path(root: Path, manifest: dict, table: str, **fmt) -> Path:
    """One concrete file. Refuses a partitioned table without its partition values —
    an unfilled `{date}` read as a path returns 'no rows', which looks like a quiet day."""
    try:
        return Path(root) / _template(manifest, table).format(**fmt)
    except KeyError as missing:
        raise LayoutError(f"{table} is partitioned by {missing}; pass it or use list_table_files()") from None


def list_table_files(root: Path, manifest: dict, table: str) -> list[tuple[dict, Path]]:
    """Every file of a table, flat or partitioned, newest partition first, deterministic."""
    tpl = _template(manifest, table)
    names = re.findall(r"{(\w+)}", tpl)
    if not names:
        p = Path(root) / tpl
        return [({}, p)] if p.exists() else []
    rx = re.escape(tpl)
    for n in names:
        rx = rx.replace(re.escape("{" + n + "}"), f"(?P<{n}>[^/]+)")
    matcher = re.compile(rx + r"\Z")
    found = []
    for p in Path(root).glob(re.sub(r"{\w+}", "*", tpl)):
        m = matcher.match(p.relative_to(root).as_posix())
        if m:
            found.append((m.groupdict(), p))
    def nat(v: str) -> tuple:                     # "slot-10" after "slot-9", dates still sort
        return tuple((0, int(p), "") if p.isdecimal() else (1, 0, p) for p in re.split(r"(\d+)", v) if p)
    return sorted(found, key=lambda vp: ([nat(vp[0][n]) for n in names], vp[1].as_posix()), reverse=True)


def partition_values(root: Path, manifest: dict, table: str, key: str) -> list[str] | None:
    """None means 'not partitioned on key' — never conflate it with 'no partitions yet' ([])."""
    if "{" + key + "}" not in _template(manifest, table):
        return None
    return sorted({vals[key] for vals, _ in list_table_files(root, manifest, table)})
```

## §5 Staged rebuild with a guarded install

```python
import hashlib, os, shutil, tempfile, time
from pathlib import Path

NEVER_INPUTS = {"run_outputs", "_provenance.json"}      # never adapter inputs, never swept


def file_hash(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_hash(p) for p in root.rglob("*")
            if p.is_file() and not (set(p.relative_to(root).parts) & NEVER_INPUTS)
            and not p.name.startswith(".")}


class Moved(Exception):
    pass


def rebuild(tenant: str, live: Path, decision_files: list[Path], build, *, attempts: int = 4) -> str:
    for _ in range(attempts):
        seed = snapshot(live)                          # BEFORE the build, not after
        base = revision(decision_files)                # from safe-writes
        with tempfile.TemporaryDirectory(dir=live.parent, prefix=".rebuild-") as tmp:
            stage = Path(tmp) / live.name
            shutil.copytree(live, stage, ignore=shutil.ignore_patterns(*NEVER_INPUTS, ".*"))
            build(stage)                                # adapter writes into stage; NO lock held
            problems = validate_tree(stage)             # the contract, on EVERY placement path
            if problems:
                kept = live.parent / f".rejected-{int(time.time())}"
                shutil.move(str(stage), kept)           # keep the evidence; never install it
                alert(f"{tenant}: rebuild rejected by the contract ({len(problems)} errors); see {kept}")
                return "rejected"
            staged = snapshot(stage)
            plan = sorted(r for r in set(seed) | set(staged) if seed.get(r) != staged.get(r))
            if not plan:
                return "unchanged"
            try:
                with tenant_lock(tenant):               # from safe-writes; milliseconds
                    if revision(decision_files) != base or any(
                            file_hash(live / r) != seed.get(r) for r in plan):
                        raise Moved()
                    for r in plan:
                        src, dst = stage / r, live / r
                        if src.exists():
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(src, dst)        # stage is a sibling: same filesystem
                        elif file_hash(dst) == seed.get(r):
                            dst.unlink()                # derived file the adapter no longer makes,
                                                        # and nobody touched it meanwhile
                return f"installed {len(plan)} file(s)"
            except Moved:
                continue                                # inputs moved mid-build: discard, retry
    return blocking_rebuild(tenant, live, build)        # must-land jobs only; under the lock
```

## §6 Provenance marker

```python
import hashlib, json, time
from pathlib import Path

FINGERPRINT_VERSION = 2          # bump when the digest's inputs change


def code_digest(adapter_dir: Path, contract_version: str) -> str:
    h = hashlib.sha256(contract_version.encode())
    for p in sorted(adapter_dir.rglob("*.py")):
        h.update(p.relative_to(adapter_dir).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def content_digest(canonical: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(canonical.rglob("*")):
        if p.is_file() and p.name != "_provenance.json" and not p.name.startswith("."):
            h.update(p.relative_to(canonical).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def stamp(canonical: Path, tenant: str, digest: str) -> None:
    """Called LAST by the adapter, so the marker only ever claims a finished build. Never raises.
    `built_at` moves only when the code OR the produced content changed — never on a no-op rebuild."""
    try:
        marker = canonical / "_provenance.json"
        new = {"tenant": tenant, "fingerprint_version": FINGERPRINT_VERSION, "digest": digest,
               "content": content_digest(canonical)}
        old = json.loads(marker.read_text()) if marker.exists() else {}
        if {k: old.get(k) for k in new} == new:
            return                                       # unchanged: do not restamp built_at
        atomic_write_text(marker, json.dumps({**new, "built_at": time.time()}))
    except Exception as exc:                             # a marker must never fail a build
        print(f"WARN provenance not stamped: {exc}")


def check(canonical: Path, digest: str) -> str:
    """current | stale | unknown. A missing or corrupt marker is UNKNOWN, never current."""
    try:
        m = json.loads((canonical / "_provenance.json").read_text())
    except (OSError, ValueError):
        return "unknown"
    if m.get("fingerprint_version") != FINGERPRINT_VERSION:
        return "unknown"
    return "current" if m.get("digest") == digest else "stale"
# CLI: exit 0 current, 3 stale/unknown (a prompt to rebuild, not a failed deploy).
```

## §7 Dropout audit (report, never repair)

```python
def dropout_audit(prev_ids: set[str], curr_ids: set[str], activity: dict[str, str]) -> list[dict]:
    """People in the previous snapshot of a reference export but not the new one,
    with INDEPENDENT liveness evidence (e.g. last badge scan read from the raw event log,
    never from the identity table being audited)."""
    rows = []
    for pid in sorted(prev_ids - curr_ids):
        last_seen = activity.get(pid)
        rows.append({"person_id": pid, "last_activity": last_seen or "",
                     "verdict": "STILL ACTIVE — export dropped them" if last_seen else "departed?"})
    return rows      # write to dropouts.csv, print a WARN with the count, keep ingesting
```

## §8 Total order and one natural key

```python
import re


def text_key(v: str) -> tuple:
    return (v.casefold(), v)                 # the raw value breaks casefold ties deterministically


def natural_key(v: str) -> tuple:
    parts = re.split(r"(\d+)", v)
    # isdecimal, not isdigit: "²" is a digit but int("²") raises
    return (tuple((0, int(p), "") if p.isdecimal() else (1, 0, p.casefold()) for p in parts if p), v)
```
Determinism proof: run the sort in child interpreters with `PYTHONHASHSEED=0..7` over a set
with casefold ties; all outputs must match; include a control showing `key=str.casefold`
alone varies. Share the comparator with the frontend and test parity (see `test-gates` templates §8).

## §9 Ingestion helpers

```python
def header_index(header: list[str], required: list[str], optional: list[str]) -> dict[str, int]:
    """Columns by NAME (case/space-insensitive). Identity columns are required; the rest are
    weather. Extra trailing columns are tolerated."""
    norm = {h.strip().casefold(): i for i, h in reversed(list(enumerate(header)))}  # first wins
    missing = [c for c in required if c.casefold() not in norm]
    if missing:
        raise ValueError(f"identity column(s) missing: {missing}")      # fail hard
    return {c: norm[c.casefold()] for c in required + optional if c.casefold() in norm}


class SkipLedger:
    """Every skipped row is counted and reported — a silent `continue` is a delete statement."""
    def __init__(self):
        self.reasons: dict[str, int] = {}

    def skip(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def report(self, source: str) -> None:
        for reason, n in sorted(self.reasons.items()):
            print(f"WARN {source}: skipped {n} row(s): {reason}")
```

## §10 Validate-before-commit ingest

```python
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,120}\.(csv|xlsx|xls|pdf)$")


def ingest_upload(tenant, raw_dir: Path, canonical: Path, upload: bytes, filename: str, run_adapter):
    name = Path(filename).name                                      # never a path from the user
    if not SAFE_NAME.match(name):
        return "rejected — unsupported file name"
    digest = hashlib.sha256(upload).hexdigest()
    final = raw_dir / f"{digest[:12]}-{name}"                       # evidence is never overwritten

    # 1. Build and validate in staging with NO lock held (seeded from live, like a rebuild).
    with tempfile.TemporaryDirectory(dir=raw_dir.parent) as tmp:
        stage_raw, stage_out = Path(tmp) / "raw", Path(tmp) / "canonical"
        shutil.copytree(raw_dir, stage_raw)
        shutil.copytree(canonical, stage_out, ignore=shutil.ignore_patterns(*NEVER_INPUTS, ".*"))
        (stage_raw / final.name).write_bytes(upload)
        baseline = revision([*raw_dir.iterdir(), *canonical.rglob("*.csv")])
        run_adapter(stage_raw, stage_out)
        if validate_tree(stage_out):
            audit({"event": "ingest-rejected", "tenant": tenant, "sha256": digest, "file": name})
            return "rejected — the result failed validation; nothing changed"

        # 2. Install under the lock only if nothing moved; idempotency checked and recorded INSIDE it.
        try:
            with guarded_install(tenant, lambda: revision([*raw_dir.iterdir(), *canonical.rglob("*.csv")]), baseline):
                if already_ingested(tenant, digest):
                    return "duplicate — already ingested"
                if final.exists():
                    return "refused — evidence with this name already exists"
                tmp_raw = final.with_name(f".{final.name}.tmp")
                tmp_raw.write_bytes(upload)
                os.replace(tmp_raw, final)                           # raw becomes permanent only now
                install_changed_files(stage_out, canonical)          # per-file atomic swap + backup
                record_ingested(tenant, digest)
        except Moved:
            return "refused — the data changed while this was being checked; upload again"
    audit({"event": "ingest-applied", "tenant": tenant, "sha256": digest, "file": final.name})
    return "applied"
```

## §11 Postgres translation

```sql
-- The contract as a template table: columns + ERROR-level constraints.
CREATE SCHEMA IF NOT EXISTS contract;
CREATE TABLE contract.ratings (
  tenant_id text NOT NULL,
  person_id text NOT NULL,
  skill     text NOT NULL,
  variant   text NOT NULL DEFAULT '',              -- nullable dimension made total for the grain
  pct       numeric NOT NULL CHECK (pct >= 0),     -- floor = ERROR; the ceiling is a WARN query below
  status    text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','WITHDRAWN')),
  build_run_id bigint NOT NULL,
  PRIMARY KEY (tenant_id, person_id, skill, variant)
);

-- Each build writes its own table; readers only ever see the view in `canonical`.
CREATE TABLE builds.ratings_r42 (LIKE contract.ratings INCLUDING ALL);
-- … load build 42 (COPY), then run the WARN-level checks below against builds.ratings_r42 …

BEGIN;
SELECT pg_advisory_xact_lock(hashtext('tenant:' || :'tenant'));   -- psql variable, quoted
-- re-check the input versions you built from; ROLLBACK if they moved
CREATE OR REPLACE VIEW canonical.ratings AS SELECT * FROM builds.ratings_r42;
COMMIT;      -- keep the previous build's table as the accident net; drop old builds by policy
```

Set-based validation (fast on large tables — never row-by-row through pydantic):

```sql
-- ERROR: duplicate grain (also enforced by the PK; useful for tables loaded without one)
SELECT tenant_id, person_id, skill, variant, count(*) FROM builds.ratings_r42
GROUP BY 1, 2, 3, 4 HAVING count(*) > 1;
-- ERROR: dangling reference
SELECT r.person_id FROM builds.ratings_r42 r
LEFT JOIN builds.people_r42 p USING (tenant_id, person_id) WHERE p.person_id IS NULL;
-- WARN: above the soft ceiling
SELECT count(*) FROM builds.ratings_r42 WHERE pct > 200;
-- WARN: coverage — share of active people with at least one rating
SELECT 1 - count(DISTINCT r.person_id)::numeric / NULLIF(count(DISTINCT p.person_id), 0)
FROM builds.people_r42 p LEFT JOIN builds.ratings_r42 r USING (tenant_id, person_id);
```
