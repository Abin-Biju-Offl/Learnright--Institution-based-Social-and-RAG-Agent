# Architecture DNA

A field manual distilled from a production system: a multi-tenant, AI-assisted
operations platform, built mostly by AI coding agents under strict human review. Everything
here is domain-neutral and safe to reuse. Every template in the companion skills is written
fresh, and no names, data or code from the source system appear.

- **This document** gives the whole picture: what the system is, the mental models, how the
  parts fit, the rules, the failure modes, the lessons, and what to improve.
- **`skills/`** holds the executable detail: one Claude Code skill per category, each with
  principles, recipes, checklists, anti-patterns, templates in the reference stack, and
  translations to FastAPI · React/TS · Postgres/pgvector · LangGraph/MCP · Docker · GitHub
  Actions · Cloud Run.

Start with §1–§3 to build the mental model. Use §4 as the map into the skills, and §5–§10 as
the checklist of hard-won rules. To apply it to a new repository, load `architecture-bootstrap`.

---

## 1. The archetype

The reference system serves several **tenants**, physical sites that each run their own
operation. Each tenant has its own messy source systems: spreadsheet exports, an ERP API,
badge scanners, PDFs. Domain experts make daily decisions about people, plans and resources.

The system has three programs that share **one data store per tenant** and **one set of
deterministic capabilities**:

| Program | What it is | What it does |
|---|---|---|
| **Capabilities ("skills")** | Standalone deterministic programs (CLIs/functions) | Read the canonical data and write reports and proposals: planning, daily re-planning, forecasting, skills-gap analysis, rebalancing |
| **The console** | A web app on touch tablets used in working conditions | Experts read the state and **record decisions** (approvals, overrides, corrections) |
| **The chat agent** | An LLM bot in a chat platform | Runs the capabilities and relays their results. **It computes nothing itself.** File uploads go through a code-controlled, human-confirmed write path |

Around those three programs sit the supporting pieces:

- **Capture pipelines** pull from each source on schedules.
- **Adapters** turn raw captures into a **canonical contract**.
- **Human decision logs** are replayed over the derived data after every rebuild.
- **Deployment**: one isolated host per tenant, code shipped as an immutable artifact,
  data backed up upward.
- **The workbench** builds it: coding-agent rules, a reviewer agent, a hard-rules
  checklist, and test gates.

The design driver is scale. Each new tenant must cost **one adapter plus one small
manifest**: never a fork, never an edit to the shared core.

---

## 2. The five mental models

### 2.1 Two truths: code and data have different sources of truth

| Class | Source of truth | Routine direction |
|---|---|---|
| Code | version control | repo → artifact → host (the host has no VCS) |
| Data: raw captures, derived canonical data, human decisions | the **running system** | host → backup, additive, a few times a day |
| Recovery | backup | backup → host, once, through a gated command that refuses while services run |
| Secrets | a secret manager | rendered per host at deploy time, never stored in the repo tree |

Derived data is data, so it lives inside the data tree, never in the code tree. No feature
pushes data down to a running host as a routine step, because that would overwrite live
captures and live decisions. → `code-data-boundaries`

### 2.2 Product vs workbench: who reads this file?

**Would production at 3am be worse off without this file?** If not, it is workbench: docs,
coding-agent rules, CI config, the journal. Workbench stays in version control and out of the
deploy artifact. Two corollaries:

- **Read-denied is not the same as workbench.** Code the product executes must ship, even
  when its agent is forbidden to read it.
- **The runbook ships.** Its audience is the operator on the host.

The repo holds **two kinds of agents**. Coding agents discover their instructions by file
location. The product agent's instructions are **declared in code and generated from
configuration**. → `code-data-boundaries`, `agentic-workbench`, `llm-agent-product`

### 2.3 Converge vs diverge: one core, many adapters

| Must converge (shared, ships once) | Should diverge (per tenant) |
|---|---|
| engine and math | raw data and its quirks |
| the canonical contract and validator | vocabulary and schema mapping |
| guardrails | which capabilities run |
| UI and agent frameworks | pace |

Adapters share no code with each other, only the contract they emit. Variance is pushed as
far left as possible:

**canonical column > manifest constant > named strategy > code**

The rule of two applies: no extension point until a second tenant needs it.
→ `multi-tenant-platform`, `canonical-data-pipeline`

### 2.4 Humans decide; software informs; nothing captured is deleted

- **Authority stack.** Template → authored or observed version → approved decision →
  schedule → execution. Each layer down is more specific and wins *for the question it
  answers* (the schedule decides **when**, not **who**; the approval decides **who**, not
  how the unit is built).
- **Detectors** report contradictions and genuine absences, never a difference a human chose.
- **Suggestions are not decisions.** Accepting one *is* authoring, and a denial is
  recorded as a decision.
- **Never delete information.** "Off" means stop reading the data, not clearing it. A
  withdrawal is a row, an undo is a reopen row, and backups are an accident net.

→ `human-decision-authority`, `decision-ledger`, `readiness-detectors`

### 2.5 Evidence over prose

A claim counts as verified only once you have seen it fail:

- a regression test must fail at the merge base, on the assertion that names the bug;
- a gate must be mutation-checked;
- "no behaviour change" must be backed by a per-record diff on real data.

Prose does not run, so facts that can run belong in tests, registries and generated
context. Prose records **why**, and what was tried and rejected.
→ `test-gates`, `agentic-workbench`, `engineering-journal`

---

## 3. System anatomy

```
 sources (ERP API, exports, scanners, PDFs)
        │  capture pipelines (scheduled; byte-faithful; per source/key/date)
        ▼
 ┌──────────── per-tenant DATA TREE (owned by the host) ──────────────────────────┐
 │ raw/…                  evidence: append; never edited                          │
 │ decisions/…            human decision logs: append-only, latest row wins       │
 │ canonical/…            derived: adapter output, validated, provenance-marked   │
 │   ↑ adapter (one per source family) ← staged rebuild + guarded install         │
 │   ↑ decisions replayed on every rebuild                                        │
 │ run_outputs/…          per-run outputs of capabilities (never inputs)          │
 └────────────────────────────────────────────────────────────────────────────────┘
        │ read                                  ▲ write (lock + precondition + audit)
        ▼                                       │
 deterministic capabilities  ◄── run by ──  chat agent (LLM: narrates, never decides writes)
        │ proposals/reports                     │
        ▼                                       │
 console (tablets): read state · see readiness issues · record DECISIONS ─────────┘
        │
 backup ▲ (host → object store, additive)        code ▼ (git archive of a main commit → host)
```

**Who writes what**

| Writer | Writes | Lock / guard |
|---|---|---|
| capture timers | `raw/` (new files) | none needed: new files and atomic replace |
| staged rebuild | `canonical/` (changed files only) | tenant lock held only to install, re-probing inputs |
| console saves | `decisions/` and derived rows | tenant lock + scoped precondition + audit |
| agent file ingest | raw (after validation) + canonical | the same tenant lock + idempotency + human confirmation |
| capabilities | `run_outputs/<id>/` | none needed: one directory per run |

---

## 4. The DNA by layer (map into the skills)

### 4.1 Boundaries — `code-data-boundaries`

- **Lockstep lists.** A new generated artifact goes into both the VCS ignore list and the
  deploy/Docker exclude list, in the same commit, enforced by a set-equality test.
- **Workbench exclusion.** Workbench files are excluded with **anchored** patterns, and the
  test **asks the transfer tool** what ships.
- **Runtime write paths** are granted and pre-created. The tests derive the grants from code
  constants.
- **Exclude gotchas.** `.git` and `.venv` take no trailing slash. Exclude the service
  user's home dotfiles. `--delete` keeps excluded paths, so remove stale ones explicitly.

### 4.2 Data pipeline and contract — `canonical-data-pipeline`

- **Capture or lose it.** Data you didn't capture is gone. Raw is evidence. Never substitute a
  different date.
- **Adapters.** Parse by column name. Identity fields fail hard; everything else degrades
  loudly. Count every skip. Quarantine uncertain matches instead of guessing.
- **The contract is executable code:**
  - required and optional columns, keys, grain, checks, ranges;
  - ERROR blocks placement, WARN surfaces it;
  - additive-only versioning;
  - opaque string keys;
  - the tenant id on every row.
- **Writes and rebuilds:**
  - writes are atomic (temp file + fsync + rename);
  - rebuilds take their baseline *before* building, seed staging from live, build unlocked,
    then install under the lock only if the inputs haven't moved.
- **Caching and provenance:**
  - skip and cache keys cover the full readable closure;
  - a provenance marker with a missing value reads as *unknown*, never *current*.
- **Hygiene:**
  - partitioning is a layout choice, not a contract change;
  - dropout audits compare per entity against independent evidence;
  - every sort uses a total order.

### 4.3 Multi-tenancy — `multi-tenant-platform`

- **Manifest = data.** A capped registry of named strategies, rule of two, degenerate constants
  instead of optional fields, materialized columns instead of per-tenant functions.
- **Declare, don't probe.** Capabilities and semantics are declared, never inferred from code
  shape or from a file that happens to exist.
- **Explicit tenant.** The tenant is an explicit parameter, resolved once. An enabled-tenants
  gate lives in code.
- **Isolation in five layers:** what ships in the artifact, the config, the OS sandbox, the
  data-access gate, and the prompt/UI.
- **Onboarding.** A scaffold with exactly-one-match anchors plus `--check`. Two definitions of
  done: data/capability and production.

### 4.4 Decisions and preservation — `decision-ledger`

- **Classify every table** as evidence, derived or decisions. Replay decisions after every
  rebuild. Enable writes only where replay is proven.
- **Decision rows** are append-only (latest per subject wins). Withdraw, supersede, deny and
  reopen are all rows. One `in_force` predicate decides what applies.
- **Key decisions on durable subjects.** Use the group, not the rotating slot; the identity,
  not the position. Standing decisions are date-less.
- **Identity vs presence.** The filter follows the user's question; the row carries the
  system's answer (a presence label). What a missing presence row means is declared per
  tenant; "no capture at all" withholds the tally. "Unrecorded" is a
  third state.
- **Unknown is a value.** Companion files are bound to their primary by digest. Undo only
  your own writes. Backups are verified by hash.

### 4.5 Authority and detectors — `human-decision-authority`, `readiness-detectors`

- **Detector rule.** Report a contradiction (two numbers for one thing) or a genuine absence,
  never a chosen difference. Before shipping a detector, run the six-question check.
- **Advisory engines:**
  - write nothing live;
  - pin today's human decisions;
  - output packages plus a value curve plus a ceiling;
  - "you may" is not "you should";
  - the browser never scores.
- **Readiness board:**
  - an issue is a root cause that fans out to the runs it affects;
  - one severity function (urgency × blocking × confidence);
  - a stale feed never suppresses checks that never read it, and unknown ≠ blocked;
  - every issue has a form, a link or a named owner;
  - snooze (recommended) has a reason and an expiry;
  - every number carries `as_of` + revision.

### 4.6 Write safety — `safe-writes`

- **The protocol:** validate (pure) → baseline → compute unlocked → lock → re-probe →
  merge "not mine + mine" → atomic install with one backup → audit → queue follow-ups.
- **Concurrency:**
  - one lock shared by every writer process, with a bounded wait and a typed "busy";
  - preconditions at the grain of the edit (rows, subjects, items);
  - a refusal returns the current tokens.
- **Refusals:**
  - messages state facts and never say "reload";
  - the client replays the user's edits;
  - every refusal is logged and counted.

### 4.7 Backend — `console-backend`

- **Shape:** v1 is a written list of simplicity rules; one write gate sits before dispatch; one
  exception→status table.
- **Identity:**
  - verified **per request** from a signed proxy assertion;
  - nothing cached on connection-scoped objects;
  - fails closed.
- **Authorization:**
  - a CSRF token per process generation;
  - reads open, writes gated, with a tenant write scope;
  - capabilities ≠ authorization.
- **Performance:**
  - caches keyed on content versions, with single flight, byte budgets and immutable outputs;
  - preconditions never cached;
  - read budgets as work-count tests.
- **Operations:**
  - three shapes of long job;
  - pre-fork workers warmed before forking;
  - keep-alive hardening;
  - a startup banner that states the resolved configuration.

### 4.8 Frontend UI system — `touch-ui-system`

- **Compliance by construction.** Closed token scales. The floors (14px text, 48px targets)
  sit on **base element selectors** at the right specificity. Opt-outs only with a reason.
  Gates fail on literal values, bypasses and dead exceptions.
- **Catalogues in code.** A component registry gated both ways, one control per concept, and
  a backlog as code with done-probes.
- **Behaviour:**
  - one feedback path, scoped to the workspace;
  - busy state comes from the transport;
  - controls are press-once;
  - conflict replay;
  - one auth-aware fetch with attempt objects and the actor pinned.
- **Theme without flashes.** Duplication is allowed only where a test compares the copies.
- **Testing.** UI logic runs under node with parity tests. Geometry and focus are checked in
  a real browser.
- **Migration order:** values → consolidate → sweep.

### 4.9 LLM agent product — `llm-agent-product`

- **Context.** Declared, not discovered: discovery switched off, one generated prompt, a skill
  allowlist through one resolver, and a test that inspects the built options.
- **The prompt is a function of config and the contract.** It names the absolute interpreter
  path, carries a standing reminder every turn, and is snapshotted by hash.
- **One backend contract.** A provider registry. Orchestration owns retries, the outbox,
  redaction and logging.
- **Layered guardrails:**
  - a tool allowlist;
  - one deny function, with an adapter per SDK hook;
  - a prompt policy;
  - egress redaction;
  - the OS sandbox.

  Source code is execute-only.
- **Honest failure:**
  - no final answer → raise;
  - one narrow retry;
  - model text never drives control flow;
  - "there is no background-task system".
- **Ask, don't substitute. Use honest verbs.**
- **The outbox** is the only artifact channel.
- **Writes stay outside the loop.** The model classifies into an enum, code checks, a human
  confirms code-rendered text, and code executes.
- **Data for improvement.** Traces → curated export → evals.

### 4.10 Release and runtime — `release-provenance`, `hardened-runtime`

- **Release line.** Ancestors of main only. The artifact is built from the commit.
- **The gate runs in the wrapper.** Skips are recorded permanently.
- **Provenance manifest:** validated before mutation, written atomically in two phases, with a
  single writer.
- **Channels:** production, development, and one named break-glass path.
- **Consent** per target, one target at a time.
- **Fleet reader.** The manifest is a claim; the supervisor is the fact.
- **Runtime sandbox.** The sandbox is a write ceiling, with per-tenant drop-ins.
- **Secrets.** Rendered via an allowlist, version pinned, never hand-edited.
- **Timers.** Templated and coalescing, with explicit time zones. Never both started-by and
  `After=`; non-idempotent delivery runs on its own timer.
- **Alerting.** One `OnFailure` template, a stdlib notifier, keyed cooldowns, loud
  non-delivery.
- **Watchdogs** probe the function, not the process.
- **Ceilings.** Memory and log caps.
- **Provisioning** is idempotent and verifies before restarting.

### 4.11 Quality system — `test-gates`, `legacy-port-migration`

- **Suites by question:**
  - fast = what the code does;
  - acceptance = right answers on real data;
  - archived = the migration proof, in no gate.
- **Registry.** Fails closed; new tests default to fast.
- **Runner and tests.** Separates failed / killed / setup-broken. Tests are hermetic: network
  off, clock pinned, deterministic order.
- **Base check.** A fails-at-base script built on `git archive` (never checkout).
- **Mutation discipline.** Put the bug back in the awkward place.
- **Fixture rules.** A fixture must differ on the tested dimension. Name the load-bearing list
  entries. Never assert a store is empty.
- **Code CI can't run.** Static gates, node execution and parity tests.
- **Retirement.** Behaviour tests over byte identity. Retire proofs only after lifting their
  invariants.

### 4.12 Agentic workbench — `agentic-workbench`

- **Knowledge routed by layer:**
  - rules file = models + non-negotiables with their *why*;
  - docs = reasoning;
  - checklist = detection;
  - skills = procedures;
  - tests pin the text.
- **Hard rules.** Each one comes from an incident, has a detection command, a grade and a
  "do not report" counterweight.
- **Isolation.** One worktree per task.
- **Reviewer agent.** Proves claims (fails at base, runs the gate, checks rules, audits tests,
  reads code last). It leaves a sandbox with a TRY-THIS walkthrough and posts one superseding
  verdict. **It never merges.**
- **Orchestration.** Run-owned worktrees with atomic leases.
- **Prose drift.** A diff-scoped prose resolver. PR bodies are written as falsifiable claims.
- **Ops agents.** The skill is the runbook; each agent handles one target, with consent per
  target.

### 4.13 Documentation — `engineering-journal`

- **One purpose per doc:** SPEC = what it is; design = why plus what was rejected; LOG =
  journal plus status history; README = status/next; RUNBOOK = procedures; plus onboarding,
  topic docs, plan docs and user guides.
- **Journal entries are headed by the lesson.** Each records numbers, wrong turns, the test
  that pins the fix, and what is still open.
- **Commit per milestone,** with journal and status in the same commit. Numbers carry their
  date and dataset.

---

## 5. Cross-cutting principles (the short list)

1. **Does adding tenant/customer #2 make #3 harder?** If yes, the design is wrong.
2. **Simple is beautiful.** Every mechanism must name the problem it removes; prefer the change that deletes more.
3. **Two truths.** Code from version control as an artifact; data owned by the running system, flowing up.
4. **Audience decides what ships**, not file type.
5. **The validator is the spec.** Prose drifts; code doesn't.
6. **Push variance left:** column > manifest constant > named strategy > code.
7. **Declared, not probed.** Capabilities and semantics live in configuration.
8. **The most specific human decision wins.** Report contradictions and absences, never chosen differences.
9. **A suggestion is not a decision.** Accepting is authoring; denying is recorded.
10. **Never delete information.** "Off" stops reading; withdrawal is a row.
11. **Unknown is a value.** Never fabricate a plausible default; "nobody said" ≠ "no".
12. **Identity is not presence.** The filter follows the question; the row carries the answer.
13. **Key decisions on durable subjects**, never on rotating labels or positions.
14. **One rule, one implementation.** Unavoidable duplicates are coupled by a test that compares the copies.
15. **Consistency by construction**, not by memory: base selectors, transport-level hooks, registries.
16. **Lock the install, never the work.**
17. **Preconditions at the grain of the edit.** Refusals keep the user's work and name what moved.
18. **A cache is an acceleration, never a second truth.** Key it on the content of everything it reads.
19. **Measure work, not milliseconds**, under the load the system's own schedule creates.
20. **Ship only reviewed, immutable artifacts.** Record provenance on the target and read it back.
21. **Health is the function working**, not the process existing. Silence must differ from success.
22. **Every runtime write path is part of the deploy contract.**
23. **The model narrates; deterministic code decides.** Writes go through code-rendered, human-confirmed paths.
24. **Ask, don't substitute.** Missing parameters are asked for; refusals are relayed and the turn stops.
25. **Seen to fail, or not verified.** Fails-at-base, mutation-checked gates, per-record diffs.
26. **A fixture must be able to express the bug.** Ask what it would produce under the old behaviour.
27. **Prose is part of the diff.** Grep for old names and numbers; generate facts from config.
28. **Every number is a claim** with a date, a dataset and the conditions it was measured under.
29. **Make backlogs, catalogues and procedures executable** so they fail when stale.
30. **Never weaken a control to fit a mistake.** Document the constraint instead; fail closed on ambiguous identity.
31. **Tooling must never eat work.** Archive instead of checkout, commit before mutating, leases instead of name globs.
32. **Order of operations is a dependency edge**, not a wall-clock offset; data migrates before the code that reads it.
33. **One definition of "today"**, in the business's time zone, tested in several zones.
34. **Totals cannot see per-key loss.** Diff per entity against independent evidence.
35. **A filter must report what it hides.** Summaries are computed before the filter.
36. **One field per question.** Status (the problem) and resolution (how it was covered) stay separate.
37. **Interactive paths have bounded latency.** Best-effort work goes to an idle-gated queue.
38. **Consent never transfers.** One explicit yes per target, per conversation.
39. **Incident procedures stay human.** Rollback and break-glass are runbooks, not agent actions.
40. **A known-false signal gets fixed, not memorised.** Always-on alarms train people to ignore alarms.
41. **Portability is the means, not the end.** Order work by the outcome it improves for users,
    not by how much generality it proves.

---

## 6. Recurring failure modes (and their countermeasures)

| Failure mode | What it looks like | Countermeasure |
|---|---|---|
| **Prose drift** | docstrings, docs, PR bodies, agent prompts and journal numbers describing a revision that no longer exists | diff-scoped prose resolver; grep for old names and numbers; generated facts; prose limited to *why* |
| **Vacuous checks** | tests that pass at base, pass on their own comment, iterate the list they guard, or recompute the production expression | fails-at-base proof; mutation in the awkward place; strip comments; parse structure; name load-bearing entries |
| **Consistency by memory** | opt-in lists of selectors, per-service gates, duplicated constants, the same rule implemented five times | base selectors; one choke point; registries; tests that compare copies |
| **Fixtures that can't express the bug** | single-valued dimensions; the same value in both sources; stubs that copy a wrong constant | "what would the old code produce?"; fixtures that differ on the dimension under test; constants checked against real data |
| **Comparing two descriptions where a human chose one** | detectors raising consistent false alarms about deliberate work | the authority stack; the six-question check; "which of A or B did a human decide?" |
| **Silent degradation** | a reassuring message over missing data; swallowed exceptions; notices hidden under modals | unknown ≠ blocked; loud non-delivery; refusals named; filters report what they hid |
| **Trusting proxies** | `is-active`, a notifier exiting 0, a fetch's return code, a deploy's exit code | probe the function; re-check that data landed; read back claim vs fact |
| **Fixing one site, missing its siblings** | read path fixed but not the write path; one of two save doors; a sixth reader | enumerate doors, readers and layers; test equivalent paths as a pair |
| **Samples reported as totals** | one tenant measured, a cold sample on a VM, a 5-minute window | scope every claim; measure at production duty cycle; warm, on the real machine |
| **Merges that compose wrongly** | two green branches fail together; a merge strategy silently reverts a fix | run main's newer tests on the merged tree; no `-X theirs` on shared files |
| **Tooling that eats work** | cleanup by name prefix, `reset --hard` in traps, `git add -A` in shared trees | archive-based tools; leases; explicit staging; commit before mutating |
| **Over-building** | a correct 700-line feature where deleting two refusals solved it; ceremony files | rule 0; name the simpler thing; prefer deletion |

---

## 7. Lessons ledger: incident → rule (retold generically)

**Data and decisions**
- A checkbox that turned overrides "off" by writing an empty list over them destroyed a day of
  human decisions, along with the reasons typed with them.
  → "Off" stops reading; never write empty over a store.
- A fetch-triggered rebuild re-copied a standing store and wiped promotions. A whole-directory
  swap deleted files the adapter doesn't own.
  → Seed-once plus an explicit reseed; swap only validated files; never swap directories.
- A reference-data re-export retroactively dropped new joiners while every aggregate improved.
  → Per-entity dropout audit with independent liveness evidence.
- Assignments joined by position moved people onto different work after a renumbering.
  → Identify by what a thing *is*; unplaceable pins become caveats.
- A rotation anchor one week out of phase made most planned people read as absent, and the
  stub fixture hardcoded the same wrong anchor.
  → Test periodic mappings against real observations, both phases.
- A field that could never disagree with the plan was used to veto the plan, producing dozens of
  false conflicts.
  → Prove a field can disagree before treating it as evidence.
- An approval under a temporary id sat "approved, applying to nobody" after an id change.
  → Fold identities at read time; report decisions that no longer resolve.

**Authority and detectors**
- Four detectors in three days flagged deliberate expert work as defects. One treated a
  renumbering as dozens of differences; one judged against a frozen copy; one blocked units
  daily.
  → The authority stack plus the six-question check.
- The first readiness board was almost entirely "critical".
  → Blocking means blocking; group by the expert's unit of work; route by action.
- An unconstrained optimizer stopped two units to feed others for a gain that existed only in
  the objective's units.
  → Hard rules (never stop a running unit; cap losses); record the new rule.

**Writes and concurrency**
- A long solve held the tenant-wide lock and stalled every editor.
  → Compute unlocked; install under a re-probe.
- Whole-file preconditions plus a feed rewriting files every minute made "reload before saving"
  the most common complaint. Reloading destroyed the edits.
  → Scoped preconditions; refusal messages never say "reload"; client replay.
- Per-service tenant write checks were skipped by some services, and one host overwrote another
  tenant's saved run.
  → One gate before dispatch, tested structurally.
- A handler cached verified identity on a connection-scoped object; enabling keep-alive later
  made later requests inherit the first caller's identity.
  → Reset per-request state per request; test two identities on one connection.

**Release and runtime**
- Deploys rsynced the mutable checkout, and hosts recorded no commit identity. The first
  read-back found hosts far behind with no record at all.
  → Artifact from the commit; provenance manifest; fleet reader.
- A deploy phase that always read "not restarted" was a false alarm for weeks, which meant a
  genuinely half-finished deploy would have been indistinguishable from a good one.
  → Fix known-false signals immediately.
- A single health probe raced the service bind, so every deploy exited non-zero.
  → Bounded retries; red must mean red.
- `| tail` and `; echo $?` reported failed deploys as successful.
  → Nothing after the wrapper; read the log.
- An exclude with a trailing slash missed a symlinked virtualenv, and `--delete` removed the
  host's interpreter.
  → No trailing slash for paths that may be symlinks or files.
- Per-tenant secret files were neither ignored nor excluded, so every tenant's tokens landed on
  every host.
  → Secrets in both lists; render per tenant via an allowlist.
- A watchdog notifier exited 0 without delivering, its output went to `/dev/null`, and alerts
  vanished for weeks.
  → Loud non-delivery.
- A VPN daemon reported running for most of a day with no tunnel.
  → Probe the function; repair cheap-first, then reliable; cooldown; escalate.
- Automatic restarts hid repeated out-of-memory kills until the host wedged (a cache budget had
  mispriced parse costs), and the host that ran out of memory had no
  memory metrics.
  → Per-service cgroup caps; verify telemetry end to end.
- A safety guard computed "today" in UTC on a host serving a different time zone and was wrong
  for hours every day.
  → One `today()` in the business zone; multi-zone tests.

**Agents (product and coding)**
- An agent "fixing" a crash mirrored the whole data store into its output directory, which
  auto-attaches to chat.
  → Deny bulk copy and data-root overrides; the outbox skips symlinks and caps size.
- The model invented "task id … I'll report back" stories, triggered by huge tool stdout.
  → Trim tool output; "there is no background-task system", repeated every turn.
- A bare interpreter name sent the agent into fail → search → retry loops, and the training
  traces learned that loop as the procedure.
  → Absolute interpreter paths in the prompt; fix root causes before harvesting traces.
- Flipping the default LLM backend was a one-word edit that failed silently in three layers
  (not installed, no writable state dir, credential filtered out).
  → "A default is a claim that it works with no further setup."
- A UI change passed every gate while its headline button opened the wrong dialog, because the
  click Event landed in a domain parameter.
  → Static gates for browser code; handler-arity gate.
- Parallel review cleanups deleted each other's worktrees.
  → Run-owned manifests, atomic leases, exact-target cleanup.
- A cleanup trap ran `reset --hard` and destroyed a branch.
  → Archive-based base checks; never reset in tooling.
- The dominant defect during process work was prose describing code that had already changed.
  → Prose is part of the diff.

---

## 8. Anti-patterns (do not copy)

- `if tenant == "x"` in shared code. Per-tenant set literals. Optional core dimensions with
  scattered `has_x` checks.
- Implementing a feature "off" by erasing data. Tests asserting a persisted store is empty.
  Swapping whole directories.
- Treating a general source (a template, a frozen copy) as authoritative over a specific
  human decision.
- Keying decisions on rotating labels or positions. Single-valued keys for multi-valued
  relations.
- Caches keyed on hand-written input lists. Shared mutable cached values. Entry-count LRUs
  for variable-size entries.
- A lock held across a long computation. Whole-file preconditions for row edits. Refusal
  messages that say "reload".
- Unsigned identity headers. Identity cached per connection. Per-service authorization
  checks.
- Opt-in style lists (per-selector touch targets). Literal font sizes. A native `<select>`
  for long lists. Device-locale dates.
- Prompt-level bans on files that are physically present. Product context discovered by
  location. Model text in control flow. Blind retries.
- The LLM deciding whether a write fires, or writing its own confirmation text.
- Rsyncing a working tree. Deploys without recorded provenance. `--development` against
  production.
- `deploy | tail`. Health judged by process state. An alert unit with its own `OnFailure`.
  A notifier that needs the app's venv.
- A test that iterates the list it guards. String-matching a deploy config instead of asking
  the tool. Allowlisted suite-wide checks. A detection command that prints wrong numbers
  authoritatively.
- Putting a retired migration proof back in the gate to "be safe".
- Weakening a security control to accommodate an environment quirk.
- Autosave over a numeric keypad. A plausible default silently saved. A severity scale whose
  top bucket is the common case.

---

## 9. Decisions and reversals worth remembering

- **Thin tenant packs over a shared, versioned core** — the *intended* topology (in practice
  still one repository whose deploy artifact is scoped per tenant; no version pins yet), chosen
  over copy-paste repos (O(N) fixes,
  silent security drift) and over forking the engine.
- **Narrow an engine's job instead of widening its rule set.** The daily re-planner became a
  pure hole-filler. Locality became a caller-side partition, extended to nested tiers without
  the engine learning anything. Global rebalancing became a separate, advisory capability.
- **Equivalence tests left the release gate** once the system was live, but only after their
  invariants were lifted into fast tests. The archived proof is kept.
- **Storage "flat on purpose" was reversed** once a measurement showed per-request cost growing
  with history. The reversal was recorded explicitly, with numbers.
- **The source of record for a second feed flipped twice in a week.** A source-of-record choice
  is a dated measurement, kept swappable by making the partition the interface.
- **Autosave was tried and reverted the same day,** because it reset the keypad mid-entry.
- **A code fix to a guardrail false positive was rejected.** The constraint was documented
  instead of weakening the control.
- **Fetch capability was declared, withdrawn ("a fetch that can only fail is worse than none")
  and restored** once infrastructure existed, now gated per deployment.
- **Purpose lines on screens were withdrawn rather than rewritten** when they went inaccurate,
  deliberately left ungated so an open decision wouldn't freeze.

---

## 10. Known weaknesses in the reference system (do these better)

The source system is strong, not perfect. When you replicate it:

1. **Validate on every placement path.** The scheduled rebuild installed without running the
   validator. Validate the staged tree and quarantine on ERROR.
2. **Schema-check manifests.** Unknown keys were silently ignored, so typos fell back to
   defaults. Use `extra="forbid"`.
3. **One lock implementation.** Two writers shared a lock only by filename convention. Import
   one module everywhere.
4. **Keep more than one backup generation** and version the bucket. A corrupted host copy
   could otherwise replace the good backup at the next sync.
5. **Make raw captures immutable.** Write a new file per capture; never overwrite evidence in
   place.
6. **Reset per-request state per request.** See the keep-alive identity lesson, and test it.
7. **fsync staged files before replace,** and use a generation pointer when several tables
   must change together for readers.
8. **Fail CI when a "skip if node missing" test skips.** A skipped JS check is not a pass.
9. **Let the runner keep going.** Stopping at the first failing file hid everything after it.
10. **Bound the knowledge files.** The journal and the README status grew to sizes nobody can
    read. Fragment the journal, cap the status, archive older items.
11. **Run CI on the same pinned dependency set and runtime version as production.**
12. **Alert on the backup job** and on restart counts. Give every data-writing timer an
    `OnFailure`.
13. **Set the host time zone explicitly** in provisioning, or don't depend on it.
14. **Derive or test every list inside the agent prompt.** Hand-written lists drifted from the
    generated ones.
15. **Give every LLM backend the same environment scope and the same guardrail tests.** One
    backend's shell dropped tenant scope; hook wiring was untested for the default backend.
16. **Add a per-turn timeout and a per-conversation lock** to the chat transport, and keep raw
    error tails (paths, stack traces) out of user-facing messages.
17. **Gate spacing and radius tokens,** not just type and touch targets, and close the "any
    `var(--fs-*)` passes" loophole.
18. **Share the test-gate helpers.** Comment stripping and selector splitting were copy-pasted
    across a dozen tests, which breaks the one-implementation rule for the tooling itself.
19. **Make the scaffold's `--check` load the manifest and run the validator,** not just grep
    for strings.
20. **Tenant adapters must not import the console's internals.** The inverted layering blocked
    the planned core-package split.

---

## 11. Stack mapping

| Concern | Reference stack | Target stack |
|---|---|---|
| Language/runtime | Python 3.12 with pinned constraints | Python 3.12 + TypeScript |
| Data store | CSV files per tenant on the host + object-storage backup | PostgreSQL (+ pgvector) + object storage; backups/PITR |
| Contract | `schema.py` + validator | pydantic models + DB constraints + WARN-level checks |
| Web backend | stdlib `ThreadingHTTPServer`, routing tables | FastAPI + uvicorn/gunicorn; routers with dependencies |
| Identity | Google IAP signed JWT verified per request | JWT in HttpOnly SameSite cookie (own login) or the IdP/proxy JWT |
| Frontend | no-build vanilla JS + one CSS file with tokens | React + TS + Vite + Tailwind (closed scales) + TanStack Query |
| UI gates | Python regex/parse tests + node execution | ESLint/stylelint rules + vitest + Playwright |
| LLM agent | chat bot; Claude Agent SDK and other backends behind one contract | LangGraph graph; MCP server for tools; Azure OpenAI and Claude behind one provider interface |
| Guardrails | deny function + SDK hooks + systemd sandbox | tool allowlist + MCP-side checks + redaction middleware + container sandbox |
| Scheduling | systemd timers, templated units | Cloud Scheduler + Cloud Run Jobs / Container Apps jobs (explicit time zones) |
| Deploy | `git archive` → rsync over SSH → systemd, one VM per tenant | image by digest → Cloud Run / Azure Container Apps; revision labels hold provenance |
| Consent | per-VM yes in conversation; deploy-operator agent | GitHub Environments with required reviewers |
| CI | GitHub Actions running the fast suite | the same, plus evals with recorded responses |
| Secrets | secret manager → rendered root-owned env file | Secret Manager / Key Vault references pinned to a version |
| Alerting | `OnFailure` → stdlib notifier → chat | Cloud Monitoring / Azure Monitor alerts on job failures, restarts and function probes |

---

## 12. Replication playbook (summary)

Load `architecture-bootstrap` for the full ordered steps.

| Tier | When | Adopt |
|---|---|---|
| **0** | Day one | Boundaries + lockstep lists; rules file + docs map + journal; test runner + suite registry + fails-at-base + CI; atomic writes |
| **1** | First users | Contract + validator; decision ledger; safe writes + typed refusals; release line + provenance; runtime sandbox; startup banner |
| **2** | Scale | Manifests/strategies/scaffold; tenant isolation; readiness board; version-keyed caches + read budgets; fleet reader; reviewer agent; UI tokens + registry |
| **3** | AI product | Declared agent context; MCP tools; layered guardrails; writes outside the loop; traces; evals |

---

## 13. Glossary

| Term | Meaning here |
|---|---|
| tenant | an isolated customer, site or unit served by the same core |
| raw / evidence | captured source data, byte-faithful, never edited |
| adapter | per-source-family program: raw → canonical tables |
| canonical / derived | contract-validated tables rebuilt from raw + replayed decisions |
| contract | executable schema: columns, keys, grain, checks, ranges, ERROR/WARN |
| manifest | per-tenant configuration as data (+ named strategy picks) |
| strategy | a named, registered behaviour variant selected by manifest data |
| capability ("skill") | a deterministic program that reads canonical data and writes reports/proposals |
| decision log / sidecar | append-only file/table of human decisions, replayed over derived data |
| authority stack | template → authored/observed → approved → schedule → execution |
| detector | a check that emits issues about readiness or data quality |
| advisory | output that proposes and never applies |
| precondition / token | the version a client saw, checked before a write is installed |
| install guard | lock + re-probe of inputs + atomic install |
| provenance | recorded identity of what produced an artifact or deployment |
| release line | commits reachable from the protected main branch |
| break-glass | the single named, audited emergency deploy path |
| workbench | files whose audience is the builders, not production |
| gate | the test suites a release must pass (fast + acceptance) |
| fails-at-base | proof that a new test fails on the pre-change code |
| outbox | the per-request directory that is the agent's only artifact channel |

---

## 14. Skill index

| Skill | Use it for |
|---|---|
| `architecture-bootstrap` | starting or retrofitting a project; adoption order |
| `code-data-boundaries` | two truths, product vs workbench, lockstep lists, runtime write paths |
| `canonical-data-pipeline` | capture, adapters, executable contract, atomic staged rebuilds, provenance, partitioning |
| `multi-tenant-platform` | manifests, strategies, capabilities, isolation, scaffolding, onboarding |
| `decision-ledger` | never delete; append-only decisions; identity vs presence; undo; audit |
| `human-decision-authority` | authority stack; detectors vs chosen differences; suggestions; advisory engines |
| `readiness-detectors` | issue model, severity, action routing, snooze (recommended), provenance on numbers |
| `safe-writes` | locks, install guard, scoped preconditions, typed refusals, conflict replay |
| `console-backend` | minimal robust web backend: identity, write gate, caches, jobs, workers, transport |
| `touch-ui-system` | tokens, floors, static gates, registry, backlog-as-code, one control per concept |
| `llm-agent-product` | declared context, provider contract, guardrails, honest failure, writes outside the loop, traces |
| `release-provenance` | release line, artifacts, gate in wrapper, provenance manifest, channels, fleet reader |
| `hardened-runtime` | sandboxed units, secrets, timers, alerting, watchdogs, ceilings, provisioning |
| `test-gates` | suites by question, fail-closed registry, fails-at-base, hermetic tests, static gates |
| `agentic-workbench` | rules files, hard-rules checklist, reviewer agent, worktrees, ops agents |
| `engineering-journal` | docs by purpose, lesson-headed journal, status discipline, decision records |
| `legacy-port-migration` | porting under equivalence protection; break categorisation; retiring proofs |
| `synthetic-world` | seeded, declared, reproducible datasets for tests, demos and evals |
