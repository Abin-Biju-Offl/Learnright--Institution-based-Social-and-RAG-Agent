# decision-ledger — templates

## §1 Append-only decision log (files)

```python
# app/decisions.py
import csv, io, os
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["subject_key", "status", "value", "reason", "actor", "decided_at", "source"]
APPLYING = {"ACTIVE", "PRESENT", "APPROVED", "REOPENED"}   # an ALLOWLIST; a reopen row restates its value
STOPPING = {"WITHDRAWN", "SUPERSEDED", "DENIED", "CLEARED", "ABSENT"}


def append(path: Path, rows: list[dict], actor: str, reason: str, source: str) -> None:
    """Append under the tenant lock. Never rewrite, never truncate."""
    now = datetime.now(timezone.utc).isoformat()
    existing_header = _header(path)
    header = existing_header + [f for f in FIELDS if f not in existing_header]   # never narrows
    if header != existing_header and path.exists():
        _rewrite_with_header(path, header)                 # widen: same rows, more columns
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({**r, "actor": actor, "reason": reason, "decided_at": now, "source": source})
        fh.flush(); os.fsync(fh.fileno())


def effective(path: Path) -> dict[str, dict]:
    """Latest row per subject. File order breaks timestamp ties."""
    latest: dict[str, dict] = {}
    if not path.exists():
        return latest
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            latest[row["subject_key"]] = row
    return latest


def in_force(row: dict | None) -> bool:
    """THE predicate. Unknown statuses apply nothing (fail closed)."""
    return bool(row) and row.get("status", "").upper() in APPLYING
```

Usage — "withdraw" is a row, never a delete:
```python
append(log, [{"subject_key": "p:102|skill:weld", "status": "WITHDRAWN", "value": ""}],
       actor="lead@example.com", reason="re-test failed", source="console")
```

## §2 Postgres version

```sql
CREATE TABLE decisions (
  id          bigserial PRIMARY KEY,
  tenant_id   text NOT NULL,
  subject_key text NOT NULL,
  status      text NOT NULL CHECK (status IN
               ('APPROVED','WITHDRAWN','SUPERSEDED','DENIED','REOPENED','CLEARED')),
  value       jsonb,
  reason      text NOT NULL CHECK (length(trim(reason)) > 0),
  actor       text NOT NULL,
  source      text NOT NULL,
  decided_at  timestamptz NOT NULL DEFAULT now()
);
-- The table is owned by a migration role, never by the app role (owners bypass grants).
REVOKE ALL ON decisions FROM app_role;
GRANT SELECT, INSERT ON decisions TO app_role;
GRANT USAGE ON SEQUENCE decisions_id_seq TO app_role;

CREATE FUNCTION decisions_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'decisions is append-only: record a new row instead';
END $$;
CREATE TRIGGER decisions_no_update BEFORE UPDATE OR DELETE ON decisions
  FOR EACH ROW EXECUTE FUNCTION decisions_append_only();
CREATE TRIGGER decisions_no_truncate BEFORE TRUNCATE ON decisions
  FOR EACH STATEMENT EXECUTE FUNCTION decisions_append_only();

CREATE VIEW decisions_latest AS
SELECT DISTINCT ON (tenant_id, subject_key) *
FROM decisions
ORDER BY tenant_id, subject_key, decided_at DESC, id DESC;

CREATE VIEW decisions_in_force AS
SELECT * FROM decisions_latest WHERE status IN ('APPROVED', 'REOPENED');
```

FastAPI:
```python
@router.delete("/assignments/{subject_key}", status_code=204)
def withdraw(subject_key: str, body: Reason, ctx: Ctx = Depends(write_context)):
    ctx.db.execute(insert(decisions).values(tenant_id=ctx.tenant, subject_key=subject_key,
                   status="WITHDRAWN", reason=body.reason, actor=ctx.actor, source="api"))
```

## §3 Durable subject identity (not position)

```python
def station_identity(row: dict, occurrence: int) -> str:
    """What a station IS, not where it sits: renumbering does not change it."""
    norm = lambda v: " ".join(str(v or "").split()).casefold()
    return f"{norm(row['operation'])}|{norm(row['machine'])}|{norm(row['standard_minutes'])}|#{occurrence}"


def place_pins(pins: list[dict], stations: list[dict]) -> tuple[dict, list[str]]:
    """Pins follow identity; an unplaceable pin is a caveat, never a fatal error."""
    seen: dict[str, int] = {}
    index = {}
    for s in stations:
        base = station_identity(s, 0).rsplit("#", 1)[0]
        seen[base] = seen.get(base, 0) + 1
        index[station_identity(s, seen[base])] = s
    placed, caveats = {}, []
    for pin in pins:
        target = index.get(pin["station_identity"])
        if target is None:
            caveats.append(f"pin for {pin['person_id']} not placed: its station no longer exists")
        else:
            placed[target["position"]] = pin["person_id"]
    return placed, caveats
```

## §4 Read-time identity fold

```python
def fold_ids(rows: list[dict], aliases: dict[str, str], key: str = "person_id") -> list[dict]:
    """Apply ACCEPTED aliases when reading; keep the original id; never rewrite the source."""
    out = []
    for r in rows:
        new_id = aliases.get(r[key])
        out.append({**r, key: new_id, "superseded_id": r[key]} if new_id else dict(r))
    return out
```

## §5 Digest-bound companion file

```python
import hashlib, json
from pathlib import Path


def write_pair(primary: Path, primary_bytes: bytes, companion: Path, rows: list[dict]) -> None:
    atomic_write_bytes(primary, primary_bytes)                  # primary FIRST
    if rows:                                                    # empty companion would read as "none"
        atomic_write_text(companion, json.dumps({
            "primary": primary.name,
            "primary_sha256": hashlib.sha256(primary_bytes).hexdigest(),
            "rows": rows}))


def read_pair(primary: Path, companion: Path):
    data = primary.read_bytes()                                 # ONE snapshot: parse and hash it
    parsed = parse(data)
    if not companion.exists():
        return parsed, None, "no movement record for this run"
    meta = json.loads(companion.read_text())
    if meta.get("primary") != primary.name or meta.get("primary_sha256") != hashlib.sha256(data).hexdigest():
        return parsed, None, "movement record belongs to a different run; withheld"
    return parsed, meta["rows"], ""
```

## §6 Undo only your own rows

```python
def undo_run(log: Path, run_stamp: str, replaced: dict[str, bytes]) -> list[str]:
    """Take back what THIS run appended (found by its stamp); leave everyone else's rows."""
    notes = []
    with tenant_lock(TENANT):
        rows = read_rows(log)
        mine = [r for r in rows if r.get("source") == f"run:{run_stamp}"]
        if not mine:
            return ["nothing to undo"]
        write_rows_atomically(log, [r for r in rows if r.get("source") != f"run:{run_stamp}"])
        for path, original in replaced.items():
            if file_hash(path) == hash_of_what_the_run_wrote(path):
                atomic_write_bytes(path, original)
            else:
                notes.append(f"{path} was edited by someone else after the run; left as they saved it")
    return notes or ["restored"]
```
(This removes rows the system itself appended seconds ago for a decision that never took
effect — the one sanctioned removal. Human rows are never touched.)

## §7 The test that catches the anti-pattern

```python
def test_turning_overrides_off_keeps_them() -> None:
    log = tmp / "overrides.csv"
    append(log, [{"subject_key": "s1", "status": "APPROVED", "value": "p7"}], "a", "why", "console")
    before = log.read_bytes()
    run_plan(use_overrides=False, overrides_log=log)
    check(log.read_bytes() == before, "the store still holds what was captured")
    check(plan_ignored_overrides(), "the computation did not read them")
    # NEVER: check(effective(log) == {}, ...)  — that pins the data-loss bug as correct
```
