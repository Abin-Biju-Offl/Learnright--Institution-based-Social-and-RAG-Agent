---
name: console-backend
description: Build a small, robust web backend for a data-heavy internal tool (tablet consoles, operations dashboards) without a framework tax. Covers routing tables with one uniform write-handler signature and one exception-to-status map, identity verified per request from a signed proxy assertion (fail closed, never cached per connection), one write gate before dispatch (process switch, admin allowlist, CSRF per process generation, Origin check, tenant scope), capabilities vs authorization, version-keyed caches with single flight and byte budgets, work-count read budgets as tests, three shapes of long-running job, pre-fork workers warmed before fork, keep-alive hardening, a startup banner, and printed artifacts from saved state. Use when building an internal web app or API, adding auth behind an identity-aware proxy, speeding up slow reads, adding background jobs, or hardening a minimal server.
---

# Console backend: small server, hard edges

> Simplicity means removing irrelevant generalization, not weakening integrity.


**On FastAPI · React · Postgres · Cloud Run:** routers with a write router behind `Depends(require_write)`; one `@app.exception_handler(AppError)`; identity from the verified token per request; an HMAC-signed CSRF token (instances autoscale); caches keyed on a DB version with per-key `asyncio.Lock`s; background work on a queue or Cloud Tasks. Templates §2, translation table at the end.

## 0. v1 simplicity rules (write them down, as a "No X" list)

No database while files + a contract suffice · no new frontend framework · no generic table
editor · **no arbitrary-row write endpoint** · no reimplementing server logic in the browser ·
no persistent workflow engine. Keep: a standard-library (or minimal) server, the canonical
data seam, the tenant lock, backup/replace, JSONL audit. Add machinery only from pilot evidence.

## 1. Shape of the server

- **Read routes** in one table; **write routes** in one `{route: handler}` dict (one source —
  a separate list of write routes drifts into a `KeyError` → 500).
- Every write handler has the same signature: `handler(tenant, payload, *, actor) -> dict`.
  Writes return `{ok, revision, backup_created, …refreshed view}` so the client needn't re-fetch.
- Errors: `{error, code?, subjects?}` from **one exception → status table** (see `safe-writes` §6).
  Unexpected → 500 with generic text; the real error goes only to the log.
- Client disconnects (`BrokenPipeError`, `ConnectionResetError`) end silently — never a fake 500.
- Static files: resolve and **contain** the path under the static root. JSON: `Cache-Control: no-store`.
- Security headers on every response: CSP `default-src 'self'`, `nosniff`, `Referrer-Policy:
  no-referrer`, `X-Frame-Options: DENY`. Download filenames: refuse `"`, CR, LF.

## 2. Identity at the edge — on every request

- Behind an identity-aware proxy, **verify its signed assertion** (JWT signature, audience,
  issuer, small clock skew, non-empty subject and email) on **every request**. Cache the
  proxy's *key set*, never the *identity*. Never read the unsigned identity header.
- **Fail closed**: missing verifier library or missing audience config → refuse. A dev
  identity is allowed **only** when no audience is configured **and** the client is loopback.
- `/healthz` is the only unauthenticated path (load-balancer probes).
- Model identity as `(provider namespace, address)`: an allowlist entry can mean "this address
  on any provider" or "this provider only"; an unrecognised namespace fails closed. Adding a
  second login provider prefixes every email; review caught that it would have silently
  demoted every admin to a viewer.
- **Per-request state is reset per request.** A handler cached the verified identity on its
  own instance; when HTTP keep-alive was enabled later, the same instance served every
  request on the connection — later requests skipped verification (and expiry) and
  inherited the first caller's identity. Proxies pool backend connections across users.
  When transport semantics change, audit every field cached on a connection-scoped object,
  and test **two requests with two different identities on one connection**.

## 3. Authorization: reads open, writes behind one gate

- Reads: any identity the proxy admitted — except endpoints that enumerate people/contacts
  (admin-only). Before opening reads to everyone, walk their call graphs to prove they write nothing.
- Writes: **one gate, in front of the dispatch table**, so a new route cannot opt out:
  1. process switch (`WRITE_ENABLED`); 2. admin allowlist; 3. CSRF token (`compare_digest`);
  4. `Origin` host == `Host`; 5. tenant write scope (writes only where human decisions survive
  the next rebuild). Test the order **structurally** (source order / router dependencies) —
  not by POSTing, which would write real data if the gate were broken. (A per-service check
  was skipped by some services, and one host overwrote another tenant's saved run.)
- **Capabilities ≠ authorization**: what the UI *offers* for a tenant comes from its
  manifest; what the server *allows* is the gate. "Hiding is presentation; the server is the
  boundary." A disabled control is a courtesy, not a guard — verify by sending the request directly.

## 4. CSRF token per process generation

Mint a random token at process start; hand it out only from `/session` to identities that can
edit. A mismatch → 403 `session-token-expired` (raised before any handler runs, so nothing was
written). The client re-fetches the session and retries **once**, only if the new token
differs from the one it sent, and refuses to replay a write if the signed-in identity changed
meanwhile ("your work is still here"). One token serves every worker (fork after minting).

**On autoscaled platforms (Cloud Run, Container Apps) a per-process token breaks**: each instance
mints its own, so a write routed to another instance looks "expired". Use a token that any
instance can verify — an HMAC over `(actor, session id, expiry)` signed with a key from the
secret manager — or the double-submit cookie pattern with `SameSite=Strict` plus the Origin
check. The same caveat applies to caches and single-flight locks: they are per instance.

## 5. Reads: profile first, then cache by version

Most slowness is repeated work (one request re-read the same library hundreds of times).
- **Parse cache** per file keyed `(path, mtime_ns, size)`, bounded by **bytes** (an
  entry-count LRU does not degrade, it collapses, when entry sizes vary 100×).
- **Single flight per key**: concurrent cold requests build once (a burst of cold requests became
  several times faster); store the result **before** releasing the flight; delete the flight
  entry only if it is still yours.
- **Derived payloads** keyed on a **whole-store fingerprint** minus run-output dirs: check →
  single flight → re-check → build → store → hand out an immutable value or a deep copy
  (a mutated cached set once inverted a gate).
- **History-wide reductions** stream rows and memoize only the answer, tagged with the
  version observed *before* computing (a mid-scan rewrite forces a recompute).
- **Preconditions bypass every cache.**
- Per-worker cache budgets are per worker — dividing one budget across workers made four
  workers slower than one.

## 6. Read budgets are tests

Assert **counts** — file opens, parses, builds, matcher constructions — as ratios of what the
work should scale with, on a fixture big enough that the old code fails (a quadratic hid at a
handful of units and showed at a dozen). Single flight: release N threads through a barrier, count builds (=1),
check every racer got the same object.

## 7. Long-running work: three shapes

| Shape | When | Rules |
|---|---|---|
| Synchronous solve | the user waits for the answer | subprocess with timeout; the solver gets `--no-network` in a read-only sandbox; one sentence to the user, details to the log; then the install guard |
| Background queue | best-effort follow-ups | one job per tenant, changed items first, runs only when idle, low priority (`nice` on the command line — not `preexec_fn` in a threaded server), **slot released in `finally`**, a `_start` seam so tests run it inline |
| Detached job | long extractions with progress | `jobs/<tenant>/<uuid>/state.json`; a server-generation id + pid liveness classify `running / interrupted / uncertain`; external side effects that may have half-happened are **uncertain, not retryable**; admission via a lock file; ids validated, paths contained |

Interactive paths have a bounded latency budget; anything that might exceed it reports what
it **deferred**.

## 8. Workers and transport

- **Pre-fork**: bind the socket, import, **warm the caches the first screen needs**, then fork
  N children (cold forks gave a p95 several times worse). Supervise: if one child dies, kill
  all and exit non-zero so the supervisor restarts the set. Fork, not spawn, when module
  state (CSRF token, caches, generation id) must be inherited. Per-process guards become
  per-worker — use lock files for anything that must be single across workers.
- **HTTP/1.1 keep-alive**: every response sets `Content-Length`; a request whose declared body
  was never read closes the connection (unread bytes become the next request line); a socket
  timeout; a larger listen backlog; gzip above ~1 KB; static files with content-addressed
  ETags and `no-cache` revalidation; don't log idle timeouts as errors. Three unoverridden
  stdlib defaults (HTTP/1.0, a tiny listen queue, no validators) produced latencies clustered
  at TCP SYN-retry backoff steps.

## 9. Self-description and artifacts

- **Startup banner**: which tenants are ready / hidden (no data on this host), the enabled
  scope, editing on/off per tenant (from the *enforcing* function, not a copy), identity mode,
  whether the dev actor is admin. ASCII only. Listing failures never stop the bind.
  ("It's running but I can't edit" had five inputs and three independent ways to be read-only.)
- **Printed artifacts** (PDF sheets): rendered in memory from **saved** server state (disable
  Print while the screen has unsaved edits), never hide an empty row, audit each print with
  its filters.

## 10. Testing the backend

In-process server on an ephemeral port for transport tests; handler instances with stubbed
request/response streams for unit tests; structural source-order assertions for the gate;
real subprocesses holding the lock for contention tests; every test fails at the merge base.

## Translation: FastAPI · uvicorn/gunicorn · Postgres · React

| Concept | Your stack |
|---|---|
| Route tables + uniform handler | `APIRouter`s; write router declared with `dependencies=[Depends(require_write)]` so no route opts out |
| Edge identity | dependency verifying the IdP/proxy JWT per request (`google.oauth2.id_token.verify_token` or your IdP's JWKS); cookie-JWT for your own login with `HttpOnly; Secure; SameSite=Lax` |
| CSRF | double-submit token or `SameSite=Strict` + Origin check on unsafe methods |
| Error map | `@app.exception_handler(Stale)` etc. → `{error, code, subjects}` |
| Single flight | `asyncio.Lock` per key (async) / `threading.Lock` per key; `cachetools` with a size-aware `getsizeof` for byte budgets |
| Cache key | DB version: `max(updated_at)` / a build-run id per tenant |
| Background jobs | arq/RQ/Celery or Cloud Tasks; job rows in Postgres with `state`, `server_generation`, `heartbeat_at` |
| Pre-fork + warm | `gunicorn --preload` with a warm-up hook; uvicorn workers |
| Security headers | Starlette middleware |
| Startup banner | log one structured line at startup with resolved config (never secrets) |

## Checklist
- [ ] Identity verified per request; nothing identity-related cached on connection-scoped objects.
- [ ] One write gate before dispatch; tenant write scope; capabilities separate from authorization.
- [ ] One exception→status table; refusals logged; 500s generic.
- [ ] Caches keyed on content versions; single flight; byte budgets; immutable outputs; preconditions uncached.
- [ ] Work-count budget tests; long jobs follow one of the three shapes.
- [ ] Startup banner states the resolved configuration.

Templates: [references/templates.md](references/templates.md).

## Related skills
`safe-writes` · `touch-ui-system` · `readiness-detectors` · `hardened-runtime` · `multi-tenant-platform`
