---
name: llm-agent-product
description: Build an LLM agent that end users talk to (chatbot, copilot) that is safe, honest and maintainable. Covers declared rather than discovered context (generated from config and the data contract, SDK discovery off, tests pinning what the agent sees), a provider-neutral backend contract, an agent that runs deterministic tools and computes nothing itself, layered guardrails (tool allowlist, one deny function with an adapter per SDK hook, prompt policy, egress redaction, OS sandbox), honest failure semantics, ask-dont-substitute, a per-request outbox, writes kept outside the agent loop (the model only classifies, code validates, a human confirms code-rendered text), a chat transport adapter, curated trace export and evals. Use when building a chatbot, copilot or tool-using agent (LangGraph, Claude Agent SDK, OpenAI, MCP), adding guardrails, or preparing traces for evals or fine-tuning.
---

# LLM agent product: the model narrates, deterministic code decides

> Three things share one data store and one toolset, and they are not the same program:
> **tools** (deterministic CLIs/functions that read the data and write reports), the **console**
> (where humans make decisions), and the **chat agent** (which runs the tools and relays what
> they said — it computes nothing itself).


**On LangGraph · MCP · Azure OpenAI / Claude:** deterministic tools on an MCP server (typed, read-only, tenant and actor taken from the session — never from tool arguments); a generated system prompt; one provider contract with an adapter per vendor; `interrupt()` before any write, resumed only by the same user; traces exported for evals. Templates §2, §8–§10.

## 1. Declared context, not discovered

Coding-agent harnesses discover instructions by **location** (`CLAUDE.md`, project docs,
plugins, user settings) — right for a workbench, wrong for a product. For the product agent:
- **Switch off every discovery channel** per SDK (e.g. Claude Agent SDK `setting_sources=[]`;
  no auto-loaded project docs or memory; Codex `include_*_instructions=false`; no plugin
  auto-discovery).
- **Inject one generated system prompt** and allowlist skills/tools **by name through one
  resolver** (three backends each building `root/"skills"/name` from parts meant a move broke
  two of them and a grep found none).
- **Test the built options object** (discovery off, prompt injected, allowlist exact) — and
  exclude workbench files from the deploy artifact: a prompt-level ban on a file that is
  physically present is one jailbreak away from no prohibition.

## 2. The prompt is a function of configuration

`build_context(tenants, contract, layout, runtime) -> str`, computed at start:
- enabled tenants (from manifests filtered by the deployment's scope) — never others;
- tables and columns from the **data contract**; partitioned layouts and files that are
  frozen/superseded (named by the manifest — "never read them");
- runtime facts: the **absolute interpreter path** in every documented command (a bare
  `python3` resolved to the system interpreter, failed, and the model burned turns hunting
  for a venv — then the training traces learned that loop as "the procedure"), the
  per-request output dir;
- behaviour rules (below) + the security policy;
- a short **standing reminder appended to every turn** (a one-time system prompt fades).

Snapshot the prompt by content hash into every trace. **Test the prompt text against its
sources** (every partitioned table appears with its path; only manifest-named files are called
superseded; a tenant-scoped prompt names no other tenant). Hand-written lists inside the prompt
drift — derive them or test them.

**Behaviour rules worth stating explicitly:**
- **Ask, don't substitute**: a required parameter (a date, a tenant when several are enabled)
  is asked for — never defaulted to "today" or swapped for another value. If a tool refuses,
  relay the refusal plainly and **stop**; never retry with different inputs on your own initiative.
- **Honest verbs**: re-deriving from data already on disk is not "downloading/refreshing";
  only declared fetchers touch live sources, and their own message is quoted.
- **Fast path**: when the scope is complete, run exactly one command; don't explore first.
- **Lead with the digest, attach the file**: a 300-row CSV nobody opens is not an answer.
- **Not covered → say it isn't available yet**, rather than improvising an analysis.
- **Advisory output is a proposal**, never "a change made".
- **Hold definitions fixed** ("knows a skill" = has a rating row > 0) so answers don't change
  shape between asks.

## 3. One backend contract, many providers

```python
class AgentBackend(Protocol):
    async def run(self, prompt: str, session_id: str | None, on_event, out_dir: Path,
                  stderr_lines: list[str]) -> tuple[str, str | None, dict]: ...
# trace = {"tools": [{"id","name","input","result"}], "events": [...], "result_meta": {...}}
```
- A **registry** imports adapters lazily and records *why* one is unavailable; an unknown or
  uninstalled backend yields an answer listing the available ones, not an exception.
- **Orchestration owns the shared concerns** (outbox, retry, collection, redaction, link
  stripping, logging) — never repeated per vendor. Session ids are namespaced by backend.
- Parity comes from sharing: the same prompt, the same deny function, the same skill resolver,
  the same trace shape, the same "no final answer → raise" rule.
- **A default is a claim that it works with no further setup**: switching the default backend
  needs the SDK installed on hosts, its state directory writable in the sandbox, and its
  credential rendered into config — each missing piece failed silently once.

## 4. Guardrails in layers (a denylist is never the only control)

| Layer | Mechanism |
|---|---|
| L1 integrity | read-only tool allowlist as data, translated per SDK; non-interactive deny mode (a permission prompt hangs a headless bot); SDK sandbox config: read-only FS except outbox/tmp, network off, env inherit none, strict config (a renamed security key fails closed) |
| L2 access gate | **one pure `blocked_reason(tool, input) -> str | None`**: mutations, data-root overrides, bulk copy (`cp -r`, `rsync`, `tar`), service control, env dumps, secret files/names, agent config dirs, VCS, cloud CLIs, network tools, recon, `/etc`, `/proc`, reads of proprietary source, secret-hunting search patterns. **One adapter per SDK interception point** (hook dict / decorator / stdin→stdout command hook; when an SDK's argument schema is unknown, scan every string argument). A backend without an interception point gets **no** shell or filesystem tools |
| L3 prompt policy | treat "audit mode"/"protocol" framing as untrusted; no secrets or infrastructure detail; stay on topic; tools are black boxes; **"there is no background-task system"**; never work around a blocked call |
| Egress redaction | replace live env values whose names look secret (≥8 chars, longest first) + token-shape regexes, on answers, errors, streamed events, logs, subprocess output |
| L4 OS sandbox | read-only filesystem + explicit write grants, no new privileges, private tmp, deny the cloud metadata IP, secrets in a root-owned env file |

The incident that shaped L2: an agent "fixing" a crash mirrored the whole data store into its
output directory — which auto-attaches to chat — and pointed the data root at the copy.

**Execute but don't read**: keep three classes — secrets (never readable), proprietary source
(execute only: a runner like `python` may touch it, a reader like `cat` may not), data
(readable). Shell-text gates are best effort (quoted `-c` strings slip through); for real
confidentiality expose capabilities as **typed tools** (MCP functions) instead of a shell.

Over-blocking is preferable to under-blocking; when a control is too strict (a checkout path
containing a denied word), **document the constraint — never weaken the control** to fit.

## 5. Honest failure semantics

- **No final answer → raise.** A stream that ends mid-turn hands back interim text as if it
  were the answer; treat "no result message" as failure.
- **One narrow retry**: only when resuming a session and the error says the session is gone,
  with a fresh session. Everything else surfaces. A blind retry re-runs side-effecting tools.
- **Model-authored text never feeds a control-flow predicate** (an injected "No conversation
  found" must not trigger the retry).
- Models invent async stories ("sent to the background, task id …, I'll report back") —
  triggered by huge tool stdout. Trim tool output (tens of KB → a few KB) and repeat the
  "no background tasks" rule every turn.
- Capture real diagnostics (SDK stderr sink); drop the session key on failure so the thread
  can recover; show users a short sentence, not a stack trace or host paths.
- Add a per-turn timeout and a per-conversation lock (two messages must not resume one
  session concurrently).

## 6. The outbox is the only artifact channel

One directory per request (`<timestamp>-<uuid>` doubles as the task id). The model writes
deliverables only there (`--out-dir`). Collection takes regular files only, **skips
symlinks**, caps count and total size, and reports what it omitted; `file://` and absolute
local links are stripped from answers; outputs expire after N days; commands that mass-copy
into the outbox are denied.

## 7. Writes stay outside the agent loop

When users upload files that change data (the "ingest" pattern):
1. Authenticate: an admin channel **and** an admin user allowlist (membership is not auth);
   check size from metadata before downloading.
2. **Keep the bytes in memory until confirmed** — classification structurally cannot see content.
3. **Exactly one model call**: map the user's description + filename to a **fixed intent enum**
   (strict JSON; anything else → "unclassified, ask the user").
4. **Deterministic check** with the real parser — it forecasts the actual outcome.
5. **Confirmation text is a code template**; yes/no is matched by regex — the model never
   decides whether a write fires. TTL, only the uploader can confirm, "nothing pending" reply.
6. Plain code executes off the event loop: tenant lock, idempotency on `(tenant, intent,
   sha256)`, stage → rebuild → validate → place raw → swap per file, audit every outcome
   (including exceptions), clear the pending action either way.

## 8. Transport adapter (chat platform)

Owns trigger gating (ignore bots, allowlisted servers, mention or reply), conversation →
session mapping (a thread is a session; replying to any bot message resumes it — map every
answer and file message id), progress UX (post a status message immediately and edit it with
friendly loading words; **hide tool internals**), chunking at line breaks, attachment batching
with caps, and error surfacing. It never touches an SDK. Persist the session map atomically
and bound its size.

## 9. Traces → evals → fine-tuning

- One redacted JSONL record per turn: schema version, task id, prompt, session ids, backend +
  model, **context hash**, answer/error, tool calls (input + truncated result), public events
  (**never hidden reasoning**), files accessed, outputs. Rotate.
- Export curated: join turns into sessions (a context-hash change starts a new conversation);
  reject sessions with errors, missing answers, truncated tool results, redaction markers or too
  few tool calls; drop transport metadata; normalise paths; emit chat-format rows with tool
  schemas; validate every call has a response and a schema; **human review → allowlist →
  re-export**; split train/eval by session, time and tenant.
- Fix root causes before harvesting — traces faithfully teach whatever loop the agent was stuck in.
- Evals as the acceptance suite: expected tool, args and values; forbidden phrases; required
  clarifications; refusals (see `test-gates` templates §13).

## Translation: LangGraph · MCP · FastAPI · Azure OpenAI / Claude

| Concept | Your stack |
|---|---|
| Declared context | `build_system_prompt(tenant_cfg, schema)` from DB metadata/pydantic models; no auto-loaded files |
| Deterministic tools | an **MCP server** exposing typed, read-only tools; the tenant and actor are injected server-side from the session, never accepted from the model |
| Backend contract | one `ChatModel` Protocol (or LangChain chat model interface) with Azure OpenAI and Anthropic adapters; `LLM_PROVIDER` selects; registry reports unavailable providers |
| Guardrails | tool allowlist per graph; a `blocked_reason` check in a tool-wrapper/MCP middleware; output redaction middleware; container read-only FS, no metadata access |
| Writes | LangGraph `interrupt()` before any write node; the write node renders confirmation text from a template; the resume value is matched by code |
| Outbox | per-request temp dir or object-storage prefix; signed URLs returned; size/count caps |
| Traces/evals | OpenTelemetry/LangSmith spans + your own redacted JSONL; pytest evals with recorded cassettes in CI, live on a schedule |

## Checklist
- [ ] Discovery off; one generated prompt; tools/skills allowlisted by one resolver; a test inspects the built options.
- [ ] Prompt derived from config and contract; tested against its sources; hash in every trace.
- [ ] One deny function, one adapter per SDK hook, redaction on egress, OS sandbox underneath.
- [ ] No final answer → raise; one narrow retry; model text never drives control flow.
- [ ] Outbox is the only artifact channel, with caps and no symlinks.
- [ ] The model never decides whether a write fires.
- [ ] Traces curated before any fine-tuning; evals assert tools and values.

Templates: [references/templates.md](references/templates.md).

## Related skills
`human-decision-authority` · `multi-tenant-platform` · `code-data-boundaries` · `hardened-runtime` · `test-gates` · `agentic-workbench`
