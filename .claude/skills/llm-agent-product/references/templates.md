# llm-agent-product — templates

## §1 Provider-neutral backend contract + registry

```python
# app/agent/backends/__init__.py
from __future__ import annotations
import importlib
from pathlib import Path
from typing import Awaitable, Callable, Protocol

EventCallback = Callable[[dict], Awaitable[None]]


class AgentBackend(Protocol):
    name: str

    async def run(self, prompt: str, session_id: str | None, on_event: EventCallback | None,
                  out_dir: Path, stderr_lines: list[str]) -> tuple[str, str | None, dict]:
        """Return (final_answer, session_id, trace). Raise if the turn produced no final answer.
        trace = {"tools": [{"id","name","input","result"}], "events": [...], "result_meta": {...}}"""


_MODULES = {"claude": "app.agent.backends.claude_api", "azure": "app.agent.backends.azure_openai"}
_LOADED: dict[str, AgentBackend] = {}
_UNAVAILABLE: dict[str, str] = {}


def get_backend(name: str) -> AgentBackend | None:
    if name in _LOADED:
        return _LOADED[name]
    if name not in _MODULES:
        _UNAVAILABLE[name] = "unknown backend"
        return None
    try:
        _LOADED[name] = importlib.import_module(_MODULES[name]).Backend()   # lazy: optional SDKs
    except Exception as exc:                                                  # record WHY
        _UNAVAILABLE[name] = f"{type(exc).__name__}: {exc}"
        return None
    return _LOADED[name]


def available() -> list[str]:
    return [n for n in _MODULES if get_backend(n) is not None]
```

## §2 Anthropic Messages API adapter (manual tool loop)

```python
# app/agent/backends/claude_api.py — Anthropic SDK; model per current guidance.
import json
import anthropic

MODEL = "claude-opus-5-5"


class Backend:
    name = "claude"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic()          # credentials from the environment

    async def run(self, prompt, session_id, on_event, out_dir, stderr_lines):
        messages = load_history(session_id) + [{"role": "user", "content": prompt}]
        trace = {"tools": [], "events": [], "result_meta": {}}
        while True:
            response = await self.client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=build_system_prompt(),             # §5 — generated, never discovered
                tools=TOOL_SCHEMAS,                       # read-only tools, strict schemas
                tool_choice={"type": "auto"},             # forced any/tool is a 400 on this model
                output_config={"effort": "high"},         # set explicitly (this model defaults to medium)
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",                      # server-side fallback on a refusal
                messages=messages,
            )
            if response.stop_reason == "refusal":
                raise RuntimeError("the model declined this request")   # surfaced, never retried blindly
            if response.stop_reason == "max_tokens":
                raise RuntimeError("the answer hit the output limit")   # never return truncated text
            trace["result_meta"]["model"] = response.model                # who ACTUALLY answered (fallbacks)
            messages.append({"role": "assistant", "content": response.content})   # full content, always
            if response.stop_reason == "pause_turn":
                continue                                                  # server paused a long turn: resume
            if response.stop_reason != "tool_use":
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                if not text:
                    raise RuntimeError("turn ended without a final answer")   # never return interim text
                session_id = save_history(session_id, messages)
                return text, session_id, trace
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                reason = blocked_reason(block.name, block.input)              # §4 — same gate for every backend
                if reason:
                    out, is_error = reason, True
                else:
                    try:
                        out, is_error = run_tool(block.name, block.input, out_dir), False
                    except Exception as exc:                               # noqa: BLE001
                        out, is_error = f"{type(exc).__name__}: {exc}", True
                out = trim(out, 4000)                                      # huge stdout breeds fabrication
                trace["tools"].append({"id": block.id, "name": block.name, "input": block.input, "result": out})
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": out, "is_error": is_error})
            messages.append({"role": "user", "content": results})          # ALL results in ONE message
```
(Claude is also reachable through Microsoft Foundry with the SDK's `AnthropicFoundry` client;
there, server-side `fallbacks` is unavailable — use the SDK's client-side refusal-fallback
middleware instead.)

**A second provider behind the same contract** (sketch — check names against your `openai`
SDK version): an Azure OpenAI adapter has the same `run()` signature and returns the same trace
shape. The differences live *inside* the adapter: tool schemas are translated to the provider's
function-calling format; a tool call arrives as `message.tool_calls[i]` with JSON-string
arguments (parse with `json.loads`, validate against the schema before running); results go back
as `{"role": "tool", "tool_call_id": …, "content": …}` messages; `finish_reason == "length"` is the
truncation case. The **same** `blocked_reason`, trimming and trace recording apply — parity comes
from sharing those, not from the vendor SDKs looking alike.

## §3 Claude Agent SDK options (mirrors a working, version-pinned integration — verify names against your installed `claude-agent-sdk`)

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher


async def pre_tool_use(input_data, tool_use_id, context):
    reason = blocked_reason(input_data.get("tool_name", ""), input_data.get("tool_input", {}))
    if reason:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
    return {}


def build_options(out_dir: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_CONTEXT},
        setting_sources=[],                          # DISCOVERY OFF: no user/project/local settings
        allowed_tools=["Read", "Glob", "Grep", "Bash"],
        disallowed_tools=["Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch"],
        permission_mode="dontAsk",                   # deny instead of prompting a headless bot
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[pre_tool_use])]},   # every tool
        cwd=str(REPO_ROOT),
        env={"PATH": f"{INTERPRETER_BIN}:{os.environ['PATH']}",                  # venv first, never .resolve()
             "CLAUDE_CONFIG_DIR": str(STATE_DIR / "claude_home")},              # SDK state in a granted dir
    )
# `env` is MERGED over the parent environment (verify for your SDK version): tool subprocesses
# inherit every secret the bot process holds. Either start the bot with a scrubbed environment
# or rely on the deny function + egress redaction — and test which one you have.
```

## §4 One deny function

```python
import re, shlex

DENY_PATTERNS = [
    (r"\b(env|printenv|set)\b\s*($|\|)", "environment dumps"),
    (r"\.env\b|id_rsa|\.pem\b|credentials", "secret files"),
    (r"\b(curl|wget|nc|ncat|ssh|scp|telnet|ftp)\b", "network tools"),
    (r"\b(gcloud|gsutil|aws|az|kubectl)\b", "cloud CLIs"),
    (r"\bgit\b", "version control"),
    (r"\bsystemctl\b|\bjournalctl\b", "service control"),
    (r"\bcp\s+(-\w*[rRa]|--(recursive|archive))|\b(rsync|tar|zip)\b", "bulk copy"),
    (r"\b[A-Z_]*DATA_ROOT=", "data-root override"),
    (r"(^|\s)/(etc|proc)(/|\s|$)", "host internals"),
]
REPO = Path("/opt/app").resolve()
SOURCE_ROOTS = (REPO / "core", REPO / "contract")   # execute-only: runners yes, readers no
RUNNER = re.compile(r"^(python3?(\.\d+)?|bash|sh)$") # matches python3.12 in a venv too


def is_source(p: str) -> bool:
    """Absolute, ./relative or ../ spellings all resolve to the same answer."""
    path = Path(p)
    full = (path if path.is_absolute() else REPO / path).resolve()
    return any(full.is_relative_to(root) for root in SOURCE_ROOTS)


def blocked_reason(tool: str, tool_input: dict) -> str | None:
    if tool in {"Write", "Edit", "NotebookEdit"}:
        return "This assistant cannot modify files."
    text = " ".join(str(v) for v in tool_input.values() if isinstance(v, str))   # unknown schema: scan all strings
    for pattern, label in DENY_PATTERNS:
        if re.search(pattern, text):
            return f"Blocked: {label}."
    if tool == "Bash":
        for segment in re.split(r"&&|\|\||[;|&\n]", tool_input.get("command", "")):
            try:
                words = shlex.split(segment)
            except ValueError:
                return "Blocked: unparseable command."
            if words and any(is_source(w) for w in words[1:] if not w.startswith("-")):
                if not RUNNER.match(Path(words[0]).name):
                    return "Blocked: source files may be executed, not read."
    if tool in {"Read", "Grep", "Glob"}:                 # these tools take ABSOLUTE paths
        path = str(tool_input.get("file_path") or tool_input.get("path") or "")
        if path and is_source(path):
            return "Blocked: source files may be executed, not read."
    return None
# Best effort by nature (quoted `sh -c "..."` strings slip through): for real confidentiality,
# expose capabilities as typed tools instead of a shell.
```

## §5 Generated system prompt

```python
def build_system_prompt() -> str:
    tenants = enabled_tenants()                         # manifests filtered by ENABLED_TENANTS
    tables = "\n".join(f"- `{name}` — columns: {', '.join(spec['required'])}"
                       for name, spec in CONTRACT.items())
    return f"""You answer questions about operations data for: {', '.join(t.id for t in tenants)}.
Never act for a tenant outside this list. If several are enabled and the user names none, ask which.

## Tables (per tenant)
{tables}
{partition_notes(tenants)}

## Commands — run exactly as written, with this interpreter: `{PYTHON_ABS}`
{tool_catalogue()}

## Rules
- A required date is asked for, never assumed. If a tool refuses, relay its words and stop.
- Re-deriving from data on disk is not "refreshing"; quote a fetcher's own message.
- When the request is fully scoped, run exactly one command.
- Lead with a short digest; attach the files.
- If something is not covered here, say it is not available yet.
- Advisory output is a proposal for a human to decide on, never a change made.
- There is no background-task system: never say you will report back later.
""" + SECURITY_POLICY


STANDING_REMINDER = "Answer from tool output only; no background tasks; ask for missing dates."


def frame_turn(user_text: str, out_dir: Path) -> str:
    return (f"{user_text}\n\n---\n[Standing instructions: {STANDING_REMINDER}]\n"
            f"[Output files: save deliverables only into `{out_dir}` (pass it as --out-dir).]")
```

## §6 Orchestrator: outbox, narrow retry, collection, redaction, log

```python
async def run_turn(prompt: str, session_id: str | None, backend_name: str, meta: dict) -> dict:
    out_dir = OUTBOX / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True)
    backend = get_backend(backend_name)
    if backend is None:
        return {"answer": f"Backend '{backend_name}' is unavailable. Available: {', '.join(available())}."}
    stderr: list[str] = []
    try:
        answer, sid, trace = await backend.run(frame_turn(prompt, out_dir), session_id, None, out_dir, stderr)
    except Exception as exc:
        if session_id and is_stale_session(exc):         # ONLY a resumed session that is gone
            answer, sid, trace = await backend.run(frame_turn(prompt, out_dir), None, None, out_dir, stderr)
        else:
            log_task(redact_obj({"task": out_dir.name, "error": str(exc), "stderr": stderr[-50:], **meta}))
            raise
    files, omitted = collect_outputs(out_dir, max_files=25, max_bytes=50 << 20)
    answer = strip_local_links(redact(answer))
    log_task(redact_obj({"task": out_dir.name, "prompt": prompt, "answer": answer, "session": sid,
                         "backend": backend_name, "context_sha256": CONTEXT_SHA, "tools": trace["tools"], **meta}))
    return {"answer": answer, "session_id": sid, "files": files, "omitted": omitted}


def is_stale_session(exc: Exception) -> bool:
    """Built from the SDK's own error fields — NEVER from model-authored text."""
    return "no conversation found" in getattr(exc, "sdk_error_text", "").lower()


def collect_outputs(out_dir: Path, *, max_files: int, max_bytes: int) -> tuple[list[Path], list[str]]:
    files, omitted, total = [], [], 0
    for p in sorted(out_dir.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue                                     # a symlink mirror never ships
        size = p.stat().st_size
        if len(files) >= max_files or total + size > max_bytes:
            omitted.append(p.name); continue
        files.append(p); total += size
    return files, omitted
```

## §7 Egress redaction

```python
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
SHAPES = [re.compile(p) for p in (r"sk-ant-[\w-]{10,}", r"sk-[\w-]{20,}", r"gh[pousr]_\w{20,}",
                                  r"https://[\w.-]+/api/webhooks/\S+")]


def redact(text: str) -> str:
    values = sorted({v for k, v in os.environ.items()
                     if SECRET_NAME.search(k) and len(v) >= 8 and not v.isdigit()}, key=len, reverse=True)
    for v in values:                                     # longest first: no partial leftovers
        text = text.replace(v, "[REDACTED]")
    for shape in SHAPES:
        text = shape.sub("[REDACTED]", text)
    return text


def redact_obj(obj):
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj
```

## §8 Writes outside the loop: classify → check → confirm → execute

```python
INTENTS = {"roster_export", "ratings_export", "plan_upload"}     # a FIXED enum
YES = re.compile(r"^\s*(yes|y|confirm)\s*[.!]?\s*$", re.I)


async def classify(description: str, filename: str) -> str:
    """Exactly one model call; the bytes are NOT on disk and NOT in the prompt."""
    raw = await one_shot_json(f"Map to one of {sorted(INTENTS)} or 'unclassified'. "
                              f"Description: {description!r}. Filename: {filename!r}. "
                              f'Reply as JSON: {{"intent": "..."}}')
    try:
        intent = json.loads(raw)["intent"]
    except (ValueError, KeyError, TypeError):
        return "unclassified"
    return intent if intent in INTENTS else "unclassified"


def confirmation_text(intent: str, check: dict) -> str:
    return (f"I will apply **{intent}** from `{check['filename']}`: {check['rows']} rows, "    # a CODE template
            f"{check['new']} new, {check['changed']} changed. Reply **yes** within 10 minutes to apply.")


def is_confirmation(reply: str) -> bool:
    return bool(YES.match(reply))                                 # the model never decides this
```

## §9 MCP server: typed, read-only tools; tenant injected server-side

```python
# mcp_server/server.py
import os
from mcp.server.fastmcp import FastMCP

TENANT = os.environ["TENANT_ID"]      # one server process per tenant; never a tool argument
# Shared multi-tenant service instead? Serve MCP over streamable HTTP behind auth and take the
# tenant and actor from the verified request token — still never from a tool argument.
mcp = FastMCP("ops-copilot")


@mcp.tool()
def get_unit_status(unit_id: str, date: str) -> dict:
    """Stations, people, bottleneck and output rate for one unit on one date (YYYY-MM-DD)."""
    if not is_iso_date(date):
        return {"error": "date must be YYYY-MM-DD; ask the user which date they mean"}
    return unit_status(TENANT, unit_id, date)          # deterministic, read-only


@mcp.tool()
def propose_assignment(unit_id: str, date: str, absent_ids: list[str]) -> dict:
    """A PROPOSAL only. Nothing is applied; a human accepts it in the app."""
    return {"proposal": solve(TENANT, unit_id, date, absent_ids), "applied": False}


if __name__ == "__main__":
    mcp.run()
```

## §10 LangGraph: a human gate before any write (sketch — check your langgraph version)

```python
from langgraph.types import Command, interrupt


def confirm_write(state: dict) -> dict:
    text = confirmation_text(state["intent"], state["check"])       # code-rendered
    reply = interrupt({"confirm": text})                             # pauses the graph
    return {"approved": is_confirmation(str(reply))}                 # code decides


# graph = builder.compile(checkpointer=saver)        # a durable checkpointer (e.g. Postgres) in prod
# config = {"configurable": {"thread_id": chat_session_id}}   # one chat session = one thread
# graph.invoke(inputs, config)                                       # stops at interrupt
# before resuming: the replying user must be the one who started the write (check the actor
# stored in the graph state); otherwise refuse
# graph.invoke(Command(resume=user_reply), config)                   # resumes with the human's reply
```

## §11 Trace record and curated export

```python
TRACE_SCHEMA_VERSION = 3
record = {
    "schema": TRACE_SCHEMA_VERSION, "task_id": out_dir.name, "at": now_iso(),
    "source": "chat", "prompt": prompt, "resumed_session": session_id, "session_id": sid,
    "backend": "claude", "model": trace["result_meta"].get("model", MODEL), "context_sha256": CONTEXT_SHA,
    "answer": answer, "error": None,
    "tool_calls": [{"name": t["name"], "input": t["input"], "result": t["result"][:65536]} for t in trace["tools"]],
    "events": trace["events"],            # public events only — never hidden reasoning
    "output_files": [f.name for f in files],
}


def exportable(session_turns: list[dict]) -> bool:
    return (all(t["error"] is None and t["answer"] for t in session_turns)
            and not any("[REDACTED]" in json.dumps(t) for t in session_turns)
            and not any(len(c["result"]) >= 65536 for t in session_turns for c in t["tool_calls"])
            and sum(len(t["tool_calls"]) for t in session_turns) >= 1)
# export → human review → accepted-ids allowlist → re-export; split train/eval by session, time, tenant
```

## §12 Tests that pin what the agent sees

```python
opts = build_options(tmp_out)
check(opts.setting_sources == [], "the product agent discovers no settings from the filesystem")
check(opts.system_prompt["append"] == SYSTEM_CONTEXT, "the generated prompt is the one injected")

for tenant in all_manifests():
    for table, pattern in partitioned_tables(tenant).items():
        check(pattern_shown(pattern) in SYSTEM_CONTEXT, f"{tenant.id}: prompt shows {table}'s layout")

with env(ENABLED_TENANTS="t1"):
    ctx = build_system_prompt()
    check("t2" not in ctx, "a tenant-scoped prompt names no other tenant")

check(not is_stale_session(Exception("No conversation found")),
      "model-authored text cannot trigger the stale-session retry")
check(blocked_reason("Bash", {"command": "cp -a /srv/data out/"}) is not None, "bulk copy is denied")
check(blocked_reason("Bash", {"command": f"{PYTHON_ABS} core/report.py --date 2026-01-02"}) is None,
      "running a documented tool with the absolute interpreter is allowed")
```
