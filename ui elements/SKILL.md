---
name: model-switch-context-continuity
description: Guidelines for a chatbot that lets users switch between local models mid-conversation, so the session keeps its context and the new model answers consistently with the earlier conversation. Use when designing, reviewing, or debugging session handling, prompt building, context-window budgeting, or model switching.
---

# Context Continuity Across Model Switches

## 1. Core principle

**The session owns the conversation. The model does not.**

A local model is a stateless function: `(prompt) -> completion`. It remembers
nothing between calls. What feels like "memory" is the application re-sending
the history on every turn. Therefore a model switch loses context only if the
application stores history *inside* the model runtime, or in a format only one
model understands.

Design rule: keep one **model-neutral conversation record** outside any model,
and *render* it into the prompt format of whichever model is active at the
moment of each request.

```
User message
     |
     v
[Session Store]  <-- canonical, model-neutral history (source of truth)
     |
     v
[Context Builder] -- fits history into the ACTIVE model's budget
     |
     v
[Prompt Renderer] -- active model's chat template / role rules / stop tokens
     |
     v
[Active Model]  -> reply -> append to Session Store
```

Switching a model changes only the last two boxes. The store never changes.

## 2. Components and responsibilities

| Component | Responsibility | Must NOT |
|---|---|---|
| Session Store | Append-only log of messages + session metadata | Contain model-specific formatting or special tokens |
| Model Registry | Per-model facts: context limit, template type, system-role support, tokenizer, capabilities, stop sequences | Be hardcoded inside business logic |
| Context Builder | Choose which history goes into the prompt, within budget | Mutate the stored history |
| Prompt Renderer | Convert neutral messages to the model's required format | Decide what content to keep |
| Switch Handler | Change the active model safely at a turn boundary | Run during generation |
| Model Adapter | Load/unload, call the runtime, stream tokens, report errors | Hold conversation state |

Keep these as separate units. Most switching bugs come from mixing two of them.

## 3. Canonical message record

Store every message in a neutral shape:

```
{
  id:          unique, monotonic per session
  session_id:  ...
  role:        "system" | "user" | "assistant" | "tool"
  content:     plain text (plus structured parts if you support them)
  created_at:  timestamp
  model_id:    which model produced it (assistant messages only)
  token_count: {model_id: n}  -- cache, optional, may be recomputed
  flags:       {pinned, summarized, excluded, error}
}
```

Rules:
- **Append-only.** Never edit or delete history to make a model happy. Build a
  trimmed *view* instead.
- **No special tokens** (`<|im_start|>`, `[INST]`, etc.) in stored content.
  Those belong to the renderer only.
- **Record `model_id` on every assistant reply.** It is cheap, and it makes
  debugging "why did the answer change after the switch" possible.
- System prompt is stored separately from the message list (session metadata),
  so it can be re-rendered per model.
- Failed or cancelled generations are marked `error` and excluded from context.

## 4. The switch procedure

A switch is a **state transition at a turn boundary**, never mid-generation.

1. **Request**: user selects model B. Record the request; do not apply yet.
2. **Wait for a boundary**: if a generation is running, either let it finish or
   cancel it cleanly (discard the partial reply, mark it excluded). Do not swap
   weights under an active stream.
3. **Validate**: B exists in the registry and fits the machine (memory, disk).
4. **Load B** (and warm it with a tiny request if load time matters).
5. **Commit**: only after B loads successfully, set `session.active_model = B`.
   If loading fails, keep A active and tell the user. Never leave the session
   with no usable model.
6. **Unload A** (or keep it resident if memory allows and fast switch-back is
   valuable).
7. **Log a switch event** in session metadata: `{from, to, at, reason}`.
   Optionally show a small UI marker "Switched to B".
8. **Next user turn**: Context Builder runs against B's limits and template.
   No special replay step is needed, because the full history is already in the
   store.

Per-session lock: only one of {generate, switch} runs at a time for a session.
Queue the other.

## 5. Context Builder: fitting history to the new model

The new model may have a **smaller context window** than the old one. This is
the single most common cause of silently lost context after a switch.

### 5.1 Budget calculation (per request, per model)

```
available = model.context_limit
          - reserved_output_tokens      (max reply length you allow)
          - safety_margin               (5-10%, tokenizers are approximate)
          - tokens(system_prompt)
          - tokens(rendered template overhead)
history_budget = available
```

Count tokens with **the active model's own tokenizer**, not the previous
model's and not a character estimate. Different tokenizers can differ 10-30%
on the same text. If the exact tokenizer is unavailable, use a conservative
ratio and a larger margin.

### 5.2 Selection strategy (in priority order)

1. **Always include**: system prompt, pinned messages, the latest user message.
2. **Include recent turns** newest-to-oldest until the budget is reached.
   Never cut a turn in half; keep user/assistant pairs together.
3. **If older history does not fit**, represent it with a **rolling summary**
   (see 5.3) placed right after the system prompt.
4. **Optional**: retrieve relevant old messages by similarity and include them
   if budget remains (only if you already have an embedding index; not
   required).
5. If even the minimum set does not fit, tell the user the conversation is too
   long for this model and suggest switching back or starting a summarized
   session. Never silently drop the latest question.

### 5.3 Rolling summary (the lightweight long-term memory)

- Kept in session metadata, **versioned**, with a pointer to the last message
  id it covers: `{text, covers_up_to_message_id, version, written_by_model}`.
- Created when history exceeds roughly 70-80% of the *smallest* context limit
  among models the user may switch to, not only the active one. This way a
  switch to a smaller model does not trigger an expensive, blocking summary.
- Summary content: user goals, decisions made, facts the user stated (names,
  preferences, constraints), open questions, and the current task state.
  Exclude pleasantries and verbatim code unless still needed.
- Generate it with whichever model is active, but treat it as data. After a
  switch, the new model reads it like any other text.
- Never overwrite raw messages with the summary. The raw log stays; the summary
  is only a substitute inside the prompt.
- Summaries can drift. Re-summarize from the previous summary plus new
  messages, and periodically from raw history if quality matters.

## 6. Prompt Renderer: handling model differences

Different local models expect different formats. The renderer, driven by the
registry, handles:

- **Chat template**: role markers, turn separators, BOS/EOS placement. Use the
  template that ships with the model; do not hand-roll it from memory.
- **System role support**: some models have no system role. Then merge the
  system prompt into the first user message, with a clear delimiter.
- **Strict alternation**: some templates require user/assistant alternation.
  Merge consecutive same-role messages and drop empty ones in the *view*, not
  in the store.
- **Stop sequences**: set per model, so one model's end marker is not treated as
  text by another.
- **Tool/vision messages**: if the new model lacks a capability, convert
  earlier tool or image messages to a short textual description in the view
  (e.g. "[image: user shared a chart of monthly sales]"), and tell the user the
  capability is unavailable on this model.
- **Language and style**: the system prompt should state the expected style so a
  new model does not abruptly change tone. Keep that prompt model-agnostic.

## 7. Things that do NOT carry over (and what to do)

| Thing | Why it does not carry | Handling |
|---|---|---|
| KV cache / prefix cache | Tied to model weights and tokenizer | Invalidate on switch. The first reply after a switch re-processes the full prompt, so it is slower. Show a "loading / reading conversation" indicator. |
| Sampling settings | Good values differ per model | Keep per-model defaults in the registry; let the user override per session explicitly. |
| Model-side hidden state | Does not exist across calls | Nothing to do; this is why the store is the truth. |
| Tokenizer-based counts | Differ per model | Recompute on switch. Cache by `(message_id, model_id)`. |

## 8. Consistency of answers after a switch

Context continuity (the model *sees* the history) is not the same as
behavioral continuity (it *answers in the same way*). Mitigate:

- Keep the same system prompt and persona text across models.
- Include the rolling summary and pinned user facts so key details survive even
  if the older raw turns are dropped.
- Optionally add a single neutral system note on the first turn after a switch:
  "The earlier assistant replies in this conversation were written by a
  different model. Continue consistently with them." Use this sparingly; it is
  helpful for small models that otherwise restate or contradict earlier turns.
- Do not rewrite prior assistant messages to the new model's style.

## 9. Persistence and durability

- Write each message to durable storage **before** starting the next
  generation, and the assistant reply when it completes (and optionally
  checkpoint partial streams, marked incomplete).
- Persist `active_model`, switch events, system prompt, and the rolling summary
  with the session. After an app restart the session resumes with the same
  model and context.
- Use optimistic versioning on the session record (an integer revision) so two
  tabs or requests cannot silently overwrite each other's changes.
- Sessions are isolated: the builder only ever reads messages with its own
  `session_id`. Add a test for this.
- Everything is local, but still decide retention: configurable deletion, and
  no conversation text in plain application logs (log ids, counts, and timings
  instead).

## 10. Failure handling

| Failure | Behavior |
|---|---|
| Model B fails to load | Keep A active, report the reason, keep the session usable |
| Out of memory during load | Unload B, confirm A is still loaded (reload if needed), report |
| Generation error or timeout | Mark partial reply `error`, exclude from context, let the user retry |
| Prompt exceeds budget even after compaction | Return a clear message; do not truncate the latest user input silently |
| Summary generation fails | Fall back to sliding window; flag session as "degraded context" |
| Registry entry missing a field | Refuse the switch; never guess context limits |

Rule of thumb: **never lose stored data because of a model error, and never
leave the session without an active model.**

## 11. Observability

Log structured events (no message text):

- `model_switch`: from, to, duration, success/failure
- `context_built`: model, history_tokens, budget, messages_included,
  messages_dropped, summary_used (yes/no)
- `truncation`: how many messages were dropped and why
- `first_token_latency` and `total_latency`, tagged by model and by
  "first turn after switch"

Useful alarms: a rising `messages_dropped` after switches, repeated load
failures, summaries failing, or a model whose output is repeatedly empty.

## 12. Model routing (future note)

This design assumes the **user** picks the model. If automatic routing is added
later (choose a model per request by task, length, or cost), it plugs in at
exactly one point: before the Context Builder, it sets `active_model` for that
turn. Everything else in this document applies unchanged, but with two
additions: switches become frequent, so cache tokenization per model and keep
the summary threshold tied to the smallest model in the routing pool; and
record the routing decision in the `model_switch` log for auditability.

## 13. Reference flow (pseudocode, framework-neutral)

```
on_user_message(session_id, text):
    with lock(session_id):
        s = store.load(session_id)
        store.append(s, role=user, content=text)

        m = registry.get(s.active_model)
        view = context_builder.build(
            system_prompt = s.system_prompt,
            messages      = s.messages,
            summary       = s.summary,
            limit         = m.context_limit,
            reserve_out   = m.max_output,
            count_tokens  = m.tokenizer.count,
        )
        prompt = renderer.render(m.template, view, m.system_role_support)

        reply = adapter.generate(m, prompt, stop=m.stop_sequences)
        if reply.ok:
            store.append(s, role=assistant, content=reply.text, model_id=m.id)
            maybe_schedule_summary(s)
        else:
            store.append(s, role=assistant, content=reply.partial,
                         flags={error: true})
            report(reply.error)


on_switch_request(session_id, new_model_id):
    with lock(session_id):                    # waits for any generation
        s = store.load(session_id)
        if new_model_id not in registry:      return error
        if not adapter.load(new_model_id):    return error  # A stays active
        old = s.active_model
        s.active_model = new_model_id
        store.log_switch(s, old, new_model_id)
        store.save(s)
        adapter.unload(old)                   # optional / memory permitting
        warm_up(new_model_id)                 # optional
```

## 14. Verification checklist

Run these before calling the feature production-ready:

1. **Canary fact test**: tell the bot a made-up fact ("my project is called
   Zephyr-9"), switch models, ask for it. It must answer correctly.
2. **Ping-pong test**: A -> B -> A -> B over several turns; history is intact
   and ordering is correct.
3. **Smaller-window test**: build a long conversation on the large-window model,
   switch to the small-window model; the prompt must fit, the latest message
   must be present, and the summary or recent turns must preserve the canary
   fact.
4. **No-system-role test**: switch to a model without a system role; instructions
   still apply.
5. **Mid-generation switch test**: request a switch during streaming; no crash,
   no partial reply leaks into context.
6. **Failed load test**: simulate a load failure; the old model keeps working.
7. **Restart test**: kill the app after a switch; the session resumes with the
   right model and history.
8. **Isolation test**: two sessions with different models never see each
   other's messages.
9. **Token-count test**: compare estimated vs. actual prompt tokens for each
   model; the margin must be large enough that no request is rejected for
   overflow.
10. **Template test**: for each model, inspect one rendered prompt by eye
    (roles, separators, stop tokens correct).

## 15. Anti-patterns

- Storing history in the model runtime's own session/cache as the only copy.
- Storing prompts already formatted for one model's template.
- Counting tokens with the wrong tokenizer, or by characters only.
- Truncating from the *newest* end, or cutting mid-turn.
- Applying a switch while a generation is in progress.
- Marking the switch successful before the new model actually loaded.
- Overwriting raw history with summaries.
- Hardcoding context limits or templates in the code path instead of a registry.
- Assuming the first reply after a switch is as fast as later ones.
- Logging full conversation text.

## 16. Minimum viable version

If you only do five things, do these:

1. Neutral, append-only message store outside the model.
2. A registry with context limit and template per model.
3. Rebuild the prompt from the store on every turn using the active model's
   tokenizer and template.
4. Switch only at turn boundaries; commit only after a successful load.
5. Trim oldest turns when over budget (keep system prompt and the latest
   message), and add the rolling summary once that proves insufficient.