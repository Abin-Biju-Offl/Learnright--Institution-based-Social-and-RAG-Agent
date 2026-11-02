# console-backend — templates

## §1 Stdlib server skeleton (identity per request, one write gate, one error map)

```python
# app/server.py
import json, os, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CSRF_TOKEN = secrets.token_urlsafe(32)          # per process generation; forked workers share it
MAX_BODY = 2_000_000
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

READ_ROUTES = {}     # path -> fn(tenant, query, actor) -> dict
WRITE_ROUTES = {}    # path -> fn(tenant, payload, *, actor) -> dict   (ONE table: no second list)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"                # keep-alive: ONE instance serves MANY requests
    timeout = 30
    _actor_cache: str | None = None              # class defaults: send_error() may run before
    _body_read: bool = True                      # parse_request() has set anything

    def parse_request(self) -> bool:
        # Reset EVERY per-request field FIRST. Anything cached on `self` survives into the
        # next request on this connection — and proxies pool connections across users.
        self._actor_cache = None
        self._body_read = True
        ok = super().parse_request()
        if ok:
            declared = self.headers.get("Content-Length") or self.headers.get("Transfer-Encoding")
            self._body_read = not declared
        return ok

    def end_headers(self) -> None:
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        if not self._body_read:                  # unread body bytes would become the next request line
            self.close_connection = True
            self.send_header("Connection", "close")
        super().end_headers()

    # ---- identity ---------------------------------------------------------------------
    def actor(self) -> str:
        if self._actor_cache is not None:        # cached for THIS request only
            return self._actor_cache
        audience = os.environ.get("APP_JWT_AUDIENCE", "").strip()
        if audience:
            claims = verify_proxy_jwt(self.headers.get("X-Proxy-JWT-Assertion", ""), audience)
            actor = claims["email"]
        elif os.environ.get("APP_DEV_MODE") == "1" and self.client_address[0] in ("127.0.0.1", "::1"):
            # loopback alone is not enough: a reverse proxy or sidecar on the host is loopback too
            actor = os.environ.get("APP_DEV_USER", "dev@localhost")
        else:
            raise PermissionError("identity verification is not configured on this host")
        self._actor_cache = actor
        return actor

    def authorize_write(self) -> str:
        actor = self.actor()
        if os.environ.get("APP_WRITE_ENABLED") != "1":
            raise PermissionError("editing is disabled on this host")
        if not is_admin(actor):
            raise PermissionError("your identity may not edit")
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), CSRF_TOKEN):
            raise SessionTokenExpired("the edit session expired because the server restarted")
        origin, host = self.headers.get("Origin", ""), self.headers.get("Host", "")
        if not origin or urlparse(origin).netloc.casefold() != host.casefold():
            raise PermissionError("the write did not come from this app")
        return actor

    # ---- dispatch ---------------------------------------------------------------------
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        handler = WRITE_ROUTES.get(path)
        tenant = ""
        try:
            if handler is None:
                return self.reply(404, {"error": "unknown route"})
            actor = self.authorize_write()                 # BEFORE reading the body
            if self.headers.get("Transfer-Encoding"):
                return self.reply(411, {"error": "send a Content-Length; chunked bodies are not accepted"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self.reply(400, {"error": "invalid Content-Length"})
            if not 0 <= length <= MAX_BODY:
                return self.reply(413, {"error": "request too large"})
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._body_read = True
            if not isinstance(payload, dict):
                raise ValueError("expected a JSON object")
            tenant = payload.get("tenant", "")
            require_editable(tenant)                       # central tenant write scope
            self.reply(200, handler(tenant, payload, actor=actor))
        except (BrokenPipeError, ConnectionResetError):
            return                                         # client left; never a fake 500
        except Exception as exc:                           # noqa: BLE001
            status, body, headers = to_response(exc, path, tenant, self._actor_cache or "")
            self.reply(status, body, headers)                # safe-writes §6: one table, refusals logged

    def reply(self, status: int, body: dict, headers: dict | None = None) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))  # always: keep-alive framing
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 256
```

## §2 FastAPI equivalent

```python
from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.exception_handler(AppError)                  # ONE renderer keeps the {error, code} contract
async def render_app_error(request: Request, exc: AppError):
    status, body, headers = to_response(exc, request.url.path, getattr(request.state, "tenant", ""),
                                        getattr(request.state, "actor", ""))
    return JSONResponse(body, status_code=status, headers=headers)
# (raising HTTPException(409, {...}) would wrap the body as {"detail": {...}} instead)


def actor(request: Request) -> str:              # evaluated per REQUEST by construction
    token = request.cookies.get("session") or request.headers.get("X-Proxy-JWT-Assertion", "")
    return verify_jwt(token)["email"]            # raises → 401/403


def require_write(request: Request, who: str = Depends(actor),
                  x_csrf_token: str = Header("")) -> str:
    if not settings.write_enabled or not is_admin(who):
        raise PermissionDenied("editing is not allowed for this identity")
    if not verify_csrf(x_csrf_token, who):          # HMAC-signed; works across instances (SKILL §4)
        raise SessionTokenExpired("the edit session expired; your work is still here")
    return who


reads = APIRouter(dependencies=[Depends(actor)])
writes = APIRouter(dependencies=[Depends(require_write)])   # a new write route cannot opt out

# … declare every @reads.get / @writes.post route here …

app.include_router(reads, prefix="/api")          # LAST: include_router copies the routes
app.include_router(writes, prefix="/api")         # that exist at the time it is called


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response
```

## §3 Verify a proxy's signed assertion (fail closed)

```python
import os
import threading

# The proxy's published key set and issuer — take both from config (your proxy's docs list them).
PROXY_CERTS_URL = os.environ["PROXY_CERTS_URL"]
PROXY_ISSUER = os.environ["PROXY_ISSUER"]
_transport, _transport_lock = None, threading.Lock()


def verify_proxy_jwt(assertion: str, audience: str) -> dict:
    if not assertion:
        raise PermissionDenied("missing identity assertion")
    try:
        import cachecontrol, requests                                    # lazy; missing lib → refuse
        from google.auth.transport import requests as ga_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise PermissionDenied("identity verifier unavailable on this host") from exc
    global _transport
    with _transport_lock:                      # cache the KEY SET (an HTTP-caching session honours
        if _transport is None:                 # the certs' Cache-Control) — never the identity
            _transport = ga_requests.Request(session=cachecontrol.CacheControl(requests.Session()))
    try:
        claims = id_token.verify_token(assertion, _transport, audience=audience,
                                       certs_url=PROXY_CERTS_URL, clock_skew_in_seconds=30)
    except ValueError as exc:                  # bad/expired token: the library raises ValueError
        raise PermissionDenied("identity assertion rejected") from exc   # → 403, no library text
    if claims.get("iss") != PROXY_ISSUER or not claims.get("sub") or not claims.get("email"):
        raise PermissionDenied("identity assertion is incomplete")
    return claims
```

## §4 Single-flight cache with a byte budget, keyed on a store fingerprint

```python
import copy, os, sys, threading
from collections import OrderedDict

OUTPUT_DIRS = {"run_outputs"}


def store_signature(root: str) -> tuple:
    """(path, mtime_ns, size) over the WHOLE store minus run outputs — a hand-listed input
    set rots against the call graph."""
    sig = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in OUTPUT_DIRS)
        for f in sorted(filenames):
            if f.startswith("."):                  # in-flight atomic-write temps come and go
                continue
            try:
                st = os.stat(os.path.join(dirpath, f))
            except FileNotFoundError:              # replaced between listdir and stat
                continue
            sig.append((os.path.relpath(os.path.join(dirpath, f), root), st.st_mtime_ns, st.st_size))
    return tuple(sig)


class SingleFlightCache:
    def __init__(self, budget_bytes: int):
        self.budget, self.used = budget_bytes, 0
        self.items: OrderedDict = OrderedDict()            # key -> (value, cost)
        self.guard = threading.Lock()
        self.flights: dict = {}

    def get(self, key, build, cost):
        """`cost(value)` must estimate the value's real size (e.g. source bytes × a measured
        factor) — sys.getsizeof is shallow, which would turn the byte budget into an entry count."""
        with self.guard:
            if key in self.items:
                self.items.move_to_end(key)
                return copy.deepcopy(self.items[key][0])    # callers can never mutate the cache
            flight = self.flights.setdefault(key, threading.Lock())
        with flight:
            with self.guard:
                if key in self.items:                      # another thread built it meanwhile
                    return copy.deepcopy(self.items[key][0])
            value = build()
            c = cost(value)
            with self.guard:
                self.items[key] = (value, c)                # store BEFORE releasing the flight
                self.used += c
                while self.used > self.budget and len(self.items) > 1:
                    _, (_, old_cost) = self.items.popitem(last=False)
                    self.used -= old_cost
                if self.flights.get(key) is flight:
                    del self.flights[key]
        return copy.deepcopy(value)
```

## §5 Background catch-up queue (one per tenant, idle-gated, always releases)

```python
import subprocess, sys, threading, time

_running: dict[str, threading.Thread] = {}
_guard = threading.Lock()
_last_activity = time.monotonic()
IDLE_SECONDS = 3


def note_activity() -> None:          # call on every non-health request
    global _last_activity
    _last_activity = time.monotonic()


def schedule(tenant: str, items: list[str]) -> dict:
    with _guard:
        if tenant in _running and _running[tenant].is_alive():
            enqueue_front(tenant, items)          # changed items go to the front
            return {"status": "queued"}
        t = threading.Thread(target=_work, args=(tenant,), daemon=True)
        _running[tenant] = t
    enqueue_front(tenant, items)
    _start(t)                                     # seam: tests replace with an inline call
    return {"status": "queued"}


def _start(t: threading.Thread) -> None:
    t.start()


def _next_or_release(tenant: str) -> str | None:
    """Dequeue-or-exit ATOMICALLY: an item queued while the worker is leaving must not be lost."""
    with _guard:
        item = dequeue(tenant)
        if item is None:
            _running.pop(tenant, None)
        return item


def _work(tenant: str) -> None:
    try:
        while (item := _next_or_release(tenant)) is not None:
            while time.monotonic() - _last_activity < IDLE_SECONDS:
                time.sleep(0.5)                   # only when nobody is using the server
            subprocess.run(["nice", "-n", "10", sys.executable, "-m", "app.solve", tenant, item],
                           timeout=600, check=False)   # result installed via guarded_install
    finally:
        with _guard:
            if _running.get(tenant) is threading.current_thread():
                _running.pop(tenant, None)        # ALWAYS release the slot (also on an exception)
```

## §6 Detached job state

```python
INSTANCE = uuid.uuid4().hex                       # minted at import; inherited by forked workers


def job_state(job_dir: Path) -> str:
    s = json.loads((job_dir / "state.json").read_text())
    if s["status"] in ("done", "failed"):
        return s["status"]
    if s.get("instance") != INSTANCE:             # the server restarted under it
        return "uncertain" if s.get("external_side_effects_started") else "interrupted"
    if not pid_alive(s.get("pid")):
        return "uncertain" if s.get("external_side_effects_started") else "interrupted"
    return "running"
# "uncertain" is never auto-retried: reconcile with the destination first.
```

## §7 Pre-fork with warm-up and supervision

```python
def serve_forked(server: Server, workers: int) -> None:
    prewarm()                                     # build exactly what the first screen asks for
    pids = []
    for _ in range(workers):
        pid = os.fork()
        if pid == 0:
            server.serve_forever()                # children share the bound socket
            os._exit(0)
        pids.append(pid)
    pid, status = os.wait()                       # any child exits → stop the set
    for p in pids:
        if p != pid:
            os.kill(p, signal.SIGTERM)
    raise SystemExit(1)                           # let the supervisor restart everything
```

## §8 Startup banner

```python
def startup_lines() -> list[str]:
    lines = [f"app {VERSION} listening on {HOST}:{PORT}"]
    try:
        ready, hidden = tenants_with_data()
        lines.append(f"tenants ready: {', '.join(ready) or 'none'}; hidden (no data here): {', '.join(hidden) or 'none'}")
    except Exception as exc:                      # never stop the bind over a banner
        lines.append(f"tenants: could not list ({exc.__class__.__name__})")
    lines.append(f"enabled scope: {os.environ.get('ENABLED_TENANTS') or 'all'}")
    lines.append(f"editing: {'ON' if os.environ.get('APP_WRITE_ENABLED') == '1' else 'OFF'}; "
                 f"editable tenants: {', '.join(editable_tenants()) or 'none'}")   # the ENFORCING function
    lines.append(f"identity: {'proxy JWT' if os.environ.get('APP_JWT_AUDIENCE') else 'loopback dev user'}")
    return [l.encode("ascii", "replace").decode() for l in lines]   # ASCII: no code-page crashes
```

## §9 Tests worth copying

```python
# Two identities on ONE keep-alive connection must stay two identities.
conn = http.client.HTTPConnection("127.0.0.1", port)
conn.request("GET", "/api/session", headers={"X-Proxy-JWT-Assertion": jwt_for("viewer@x")})
first = json.loads(conn.getresponse().read())
conn.request("GET", "/api/session", headers={"X-Proxy-JWT-Assertion": jwt_for("admin@x")})
second = json.loads(conn.getresponse().read())
check(first["actor"] == "viewer@x" and second["actor"] == "admin@x",
      "identity is verified per request, not per connection")

# The write gate precedes the handler table, structurally (never by POSTing real data).
src = Path("app/server.py").read_text()
body = src[src.index("def do_POST"):]
check(body.index("authorize_write(") < body.index("require_editable(") < body.index("handler(tenant"),
      "auth → tenant scope → handler, in that order")

# Single flight: N racers, one build.
builds, barrier = [], threading.Barrier(12)
def racer(): barrier.wait(); cache.get("k", lambda: builds.append(1) or {"v": 1}, cost=lambda v: 64)
threads = [threading.Thread(target=racer) for _ in range(12)]
[t.start() for t in threads]; [t.join() for t in threads]
check(len(builds) == 1, f"12 concurrent cold reads built once (built {len(builds)})")
```
