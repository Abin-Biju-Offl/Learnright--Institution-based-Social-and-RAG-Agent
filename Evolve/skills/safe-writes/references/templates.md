# safe-writes — templates

## §1 Tenant lock (POSIX + Windows) and the install guard

```python
# app/safe_write.py — imported by EVERY writer process (web, bot ingest, timers, jobs)
import hashlib, os, time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Iterator

try:
    import fcntl
except ImportError:            # Windows dev boxes
    fcntl = None
    import msvcrt

LOCK_DIR = Path(os.environ.get("APP_LOCK_DIR", "/var/lib/app/locks"))


class Busy(RuntimeError):
    """Another writer owns this tenant's lock."""


class Moved(RuntimeError):
    """An input changed between the baseline read and the install."""


@contextmanager
def tenant_lock(tenant: str, timeout: float = 5.0) -> Iterator[None]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_DIR / f"{tenant}.lock", "a+b")      # fresh open: threads contend like processes
    deadline, held = time.monotonic() + timeout, False
    try:
        while True:
            try:
                if fcntl:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    fh.seek(0, os.SEEK_END)
                    if fh.tell() == 0:
                        fh.write(b"0"); fh.flush()
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                held = True
                break
            except OSError:                              # BlockingIOError is an OSError
                if time.monotonic() >= deadline:
                    raise Busy(tenant)
                time.sleep(0.1)
        yield
    finally:
        if held:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_UN)
            else:
                fh.seek(0); msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.close()


@contextmanager
def guarded_install(tenant: str, probe: Callable[[], str], baseline: str, timeout: float = 5.0):
    """Hold the lock only long enough to prove the inputs did not move, then install."""
    with tenant_lock(tenant, timeout):
        if probe() != baseline:
            raise Moved(tenant)
        yield


def revision(paths: Iterable[Path]) -> str:
    """Hash of named files, with explicit MISSING markers (absence is a state too)."""
    h = hashlib.sha256()
    for p in map(Path, paths):
        h.update(str(p).encode() + b"\0")
        if not p.exists():
            h.update(b"MISSING\0")
            continue
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()
```

## §2 Row-scoped digest

```python
import csv


def rows_digest(path: Path, match: Callable[[dict], bool], columns: list[str] | None = None) -> str:
    """Digest of only the rows this save owns. Missing file = zero rows. Blank values are
    skipped so another save widening the schema is not a 'change'. Unreadable → raise."""
    h, count = hashlib.sha256(), 0
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:      # raises if unreadable: fail closed
            for row in csv.DictReader(fh):
                if not match(row):
                    continue
                count += 1
                items = sorted((k, v) for k, v in row.items()
                               if v not in (None, "") and (columns is None or k in columns))
                h.update(repr(items).encode())
    h.update(f"rows={count}".encode())
    return h.hexdigest()[:16]
```

## §3 Per-subject tokens

```python
ABSENT = "none"      # lets a creating form claim "nothing there yet"


def subject_tokens(subjects: list[str], read_rows_for: Callable[[str], list[dict]]) -> dict[str, str]:
    """One short token per subject, read from disk/DB past every cache:
    a precondition is exactly where a stale answer does damage."""
    tokens = {}
    for s in subjects:
        rows = read_rows_for(s)
        if not rows:
            tokens[s] = ABSENT
            continue
        canonical = sorted(tuple(sorted(r.items())) for r in rows)
        tokens[s] = hashlib.sha256(repr(canonical).encode()).hexdigest()[:16]
    return tokens


def moved(expected: dict[str, str] | None, current: dict[str, str]) -> dict[str, str] | None:
    """None → client sent no tokens (fall back to the whole revision);
    {} → nothing moved; otherwise the moved subjects WITH their current tokens."""
    if expected is None:
        return None
    return {s: current.get(s, ABSENT) for s, tok in expected.items() if current.get(s, ABSENT) != tok}


class Stale(ValueError):
    def __init__(self, message: str, subjects: dict[str, str] | None = None):
        super().__init__(message)
        self.subjects = subjects or {}
```

## §4 Multi-file install with rollback and one backup generation

```python
import shutil, time, uuid


def install(pairs: list[tuple[Path, Path]]) -> dict[str, str | None]:
    """pairs = [(staged, live)]. All or nothing; keep exactly one prior generation per file.
    Staged files must already be durable: write them with atomic_write (fsync on the WRITE
    handle — fsync on a read-only handle fails on Windows)."""
    backups: dict[Path, Path | None] = {}
    for _, live in pairs:
        if live.exists():
            b = live.with_name(f"{live.name}.bak-{int(time.time())}-{uuid.uuid4().hex[:8]}")
            shutil.copy2(live, b)
            backups[live] = b
        else:
            backups[live] = None
    done: list[Path] = []
    try:
        for staged, live in pairs:
            os.replace(staged, live)
            done.append(live)
    except OSError:
        for live in reversed(done):                   # roll back atomically too
            b = backups[live]
            if b is None:
                live.unlink(missing_ok=True)
            else:
                restore = live.with_name(f".{live.name}.restore-{uuid.uuid4().hex[:8]}")
                shutil.copy2(b, restore)
                os.replace(restore, live)
        raise
    for _, live in pairs:                             # prune older generations only
        for old in live.parent.glob(f"{live.name}.bak-*"):
            if old != backups[live]:
                old.unlink(missing_ok=True)
    return {str(k): str(v) if v else None for k, v in backups.items()}
```

## §5 A save, end to end

```python
def save_assignment(tenant: str, payload: dict, actor: str) -> dict:
    changes = validate_pure(payload)                                   # no live reads, no lock
    owned = lambda: rows_digest(STORE, lambda r: r["unit"] == payload["unit"])
    baseline = owned()
    if payload.get("expected_revision") not in (None, baseline):
        raise Stale("Unit 4 was saved by someone else after you opened it, so nothing was applied.")
    with tempfile.TemporaryDirectory(dir=STORE.parent) as tmp:
        staged = Path(tmp) / STORE.name
        try:
            with guarded_install(tenant, owned, baseline):
                live = read_rows(STORE)
                kept = [r for r in live if r["unit"] != payload["unit"]]   # every row not mine
                write_rows(staged, kept + apply(changes, live))            # + mine
                backups = install([(staged, STORE)])
        except Moved:
            raise Stale("Unit 4 changed while this was saving, so nothing was applied.")
    try:
        audit({"event": "assignment-saved", "tenant": tenant, "actor": actor,
               "unit": payload["unit"], "before": baseline, "after": owned(), "backups": backups})
    except Exception:
        pass                                                   # never fail a committed save
    queue_followups(tenant, payload["unit"])                   # after release
    return {"ok": True, "revision": owned()}
```

## §6 Error mapping and refusal log (framework-agnostic)

```python
class AppError(Exception):
    """Base for every error a user may see. Anything else is a bug → generic 500."""


class UserError(AppError, ValueError): ...          # user-correctable input
class PermissionDenied(AppError): ...               # NOT the builtin PermissionError (EACCES = a bug)
class SessionTokenExpired(PermissionDenied): ...
class TooLarge(AppError): ...
# Stale and Busy (§1, §3) should also derive from AppError.

ERROR_MAP = [                      # first match wins; ONE table for the whole server
    (SessionTokenExpired, 403, "session-token-expired"),
    (Stale, 409, "stale"),
    (Busy, 503, "busy"),
    (TooLarge, 413, None),
    (PermissionDenied, 403, None),
    (UserError, 400, None),        # only DOMAIN classes: a bare ValueError/PermissionError from
]                                  # a library or the filesystem is a bug, and must not leak as 4xx


def to_response(exc: Exception, route: str, tenant: str, actor: str):
    for cls, status, code in ERROR_MAP:
        if isinstance(exc, cls):
            body = {"error": str(exc)} | ({"code": code} if code else {})
            if isinstance(exc, Stale) and exc.subjects:
                body["subjects"] = exc.subjects
            if status in (409, 503):
                try:
                    audit({"event": "save-refused", "route": route, "code": code,
                           "tenant": tenant, "actor": actor, "message": str(exc)[:300]})
                except Exception:
                    pass
            headers = {"Retry-After": "5"} if status == 503 else {}
            return status, body, headers
    log_exception(exc)
    return 500, {"error": "Something went wrong on the server; nothing was changed."}, {}
```

## §7 Postgres + FastAPI translation

```python
@router.put("/units/{unit_id}/assignment")
def put_assignment(unit_id: str, body: AssignmentIn, if_match: str = Header(...),
                   ctx: Ctx = Depends(write_context)):
    try:
        expected = int(if_match.strip().removeprefix("W/").strip('"'))   # ETags arrive quoted: "3"
    except ValueError:
        raise UserError("If-Match must carry the version you opened")
    result = ctx.db.execute(text("""
        UPDATE assignments SET data = :data, version = version + 1, updated_by = :actor
        WHERE tenant_id = :t AND unit_id = :u AND version = :v
        RETURNING version"""),
        {"data": body.model_dump_json(), "actor": ctx.actor, "t": ctx.tenant,
         "u": unit_id, "v": expected}).first()
    if result is None:
        current = ctx.db.scalar(text("SELECT version FROM assignments WHERE tenant_id=:t AND unit_id=:u"),
                                {"t": ctx.tenant, "u": unit_id})
        # a domain exception, rendered by the ONE exception handler (keeps {error, code, …};
        # HTTPException would wrap it as {"detail": …})
        raise Stale("Saved by someone else after you opened it; nothing was applied.",
                    subjects={f"unit:{unit_id}": str(current)})
    return {"version": result.version}
```
