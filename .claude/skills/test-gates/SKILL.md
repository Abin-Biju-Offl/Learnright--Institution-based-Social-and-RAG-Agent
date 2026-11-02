---
name: test-gates
description: Build a test system whose green actually means something. Covers suites named by the question they answer (fast / acceptance / archived), a fail-closed suite registry, check-collecting standalone tests, a runner that separates failed vs killed vs setup-broken, hermetic tests (network off, clock pinned, deterministic order), proving a regression test fails at the merge base, mutation-checking your own guards, fixture-design rules, static gates for code CI cannot execute (browser JS/CSS/HTML, unit files, prompts, configs), parity tests between two implementations, verification without an oracle, work-count performance tests, and retiring a migration proof without losing its invariants. Use when setting up tests in a new repo, writing a regression test, reviewing tests, deciding what blocks a release, or when "everything was green" and a feature still shipped broken.
---

# Test gates: evidence, not decoration

> A test is evidence only after you have watched it fail for the reason its name gives.
> A green gate is the floor, not the goal.

Every rule below exists because a test that satisfied the *letter* of "the PR has tests"
let a real defect through. Most were caught later by a reviewer asking one of three
questions, which you should ask first:

1. **What would this fixture produce under the OLD behaviour?** If "the same", the test pins nothing.
2. **Would this test fail if the thing it guards were removed** (or the function body deleted)?
3. **Have I seen it fail at the merge base, on the assertion that names the bug?**

---


**On pytest · vitest · Playwright · GitHub Actions:** a `conftest.py` that refuses unmarked private-data tests (templates §10), the fails-at-base script running `pytest`, record/replay LLM evals as an acceptance suite (§13), and one CI workflow for all of it (§14).

## 1. Name suites by the question they answer

| Suite | Question it answers | Needs | Runs |
|---|---|---|---|
| `fast` | What does the code **do**? | the repo only (synthetic fixtures) | every commit, CI on every PR |
| `acceptance` | Does each capability still give a **right answer on real data**, and do humans' recorded decisions survive the machinery? | the real/private dataset, **and nothing else** | every commit locally + the release gate |
| `archived` (equivalence / migration proof) | Did the port match the legacy system byte-for-byte? | legacy checkout + data | **in no gate**; kept runnable |

Rules:
- Name suites by *question and dependency*, never by mechanism ("oracle", "integration").
  When a name stops being true, rename it and pin that the old name is gone.
- The **release gate = fast + acceptance**. It asks "does what works today still work?" — a
  regression question. A migration proof answers a question that is over once you are live.
- An acceptance failure is never "replaced" by a fast pass.
- The suite that needs private data must need **nothing else** (no legacy repo, no network).
  Make that a tested property, not an accident.

## 2. One registry, fail closed

- Discover tests by glob. **New tests default to `fast`**; tests needing private data are
  registered *by hand* into `acceptance` (this is the trap: forget it and the test passes on
  your machine and fails for everyone else — CI without the data is what catches it).
- The registry **refuses to run** if it names a missing file, names a file twice, or the
  partition does not cover every discovered file.
- Test the suites' defining property **in both directions**: every acceptance file reads the
  private-data root and none reads the legacy repo; every archived file reads the legacy repo.
  Two directions guard each other — a broken predicate that always returns False passes one
  and fails the other.
- Pin the gate script's composition by parsing it (comments stripped): it chains fast and
  acceptance, never archived.

## 3. The test file shape

Standalone, executable, one behaviour per file (pytest is fine too — the discipline is the point):

- A module docstring that states the behaviour as a sentence, **tells the incident** (what
  broke, why existing tests missed it), and records the base result:
  `Fails at <base-sha> with "<assertion text>" (BASE_EXIT=1). Run: python tests/test_x.py`.
- A `check(ok, msg)` helper that **collects** failures and prints `ok`/`FAIL` per check;
  exit non-zero at the end with a count. **Never abort the file**: a `next(...)` that raises,
  or an early `return`, hides every check below it. Guard lookups; wrap each sub-test so a
  crash is one failure, not an aborted file.
- File names state the behaviour (`test_refusal_keeps_user_edits.py`, not `test_utils2.py`).
- Each file runs in its own process so one file cannot poison another's state.

Templates: [references/templates.md](references/templates.md) §1.

## 4. The runner: three outcomes, three exit codes

| Outcome | Meaning | Exit |
|---|---|---|
| failed | an assertion said no | 1 |
| setup broke | registry invalid, interpreter missing, harness error | 2 |
| **killed** | a signal ended the process — **no verdict was produced** | 3 |

A signal death reported as `FAILED (exit -15)` (rendered 241 by a shell) sends people
hunting a bug the branch does not have. Print `KILLED: <test> — re-run before blaming the
change`. Test the mapping with a real child process killed by SIGTERM.

Also: a suite that cannot run reads exactly like a suite that passes — print the count of
files run and fail on "0 tests collected". Prefer a `--keep-going` mode that reports every
failing file (stopping at the first hides the rest).

## 5. Hermetic by construction

- **Network off for the whole process tree**: point `HTTP(S)_PROXY` (both cases) at a dead
  local port and clear `NO_PROXY`. Environment inheritance reaches nested subprocesses that
  no CLI flag can. A comparison test that phones a live API goes red or green *by the day*.
- **Time is configuration**: one `today()` seam; dates are calendar dates, not instants; run
  date logic under several timezones (UTC, one west, one east) and require identical output.
  A guard that took "today" from a UTC timestamp was wrong for hours every day on one host
  and invisible on another.
- **Determinism**: set iteration and hash order leak into output — sort with a *total* key,
  pin `PYTHONHASHSEED` when diffing, and run base-vs-base before claiming base-vs-head.
- **Private data is resolved, never copied**: resolve data roots from a well-known location
  relative to the main checkout (e.g. sibling directories) only when unset; worktrees never
  get copies; CI's lack of data is your portability check.

## 6. Prove the regression test fails at base

One tested script, `prove-fails-at-base <base> <test>` (template §5):
- Extract the base commit with `git archive` into a temp dir; overlay **only the new test**;
  run it with the current interpreter by absolute path. **Never checkout/detach/reset** — a
  restore step can silently eat uncommitted work, and a `trap … reset --hard` once destroyed a branch.
- Print `BASE_EXIT=<n>` for every test outcome; print `SETUP FAILED` (exit 2, no marker)
  when the harness itself could not run. A missing marker is never "the bug reproduced".
- Required outcome: **base fails on the assertion that describes the bug, head passes.**
  An import error at base (the PR adds a function) is *inconclusive*: reduce to a behavioural
  probe — call the changed function at base and show the wrong value.
- Put the base failure text in the PR body. **N claimed defects need N pinned checks**, or say
  which are unpinned and why.
- If the branch fixed something mid-way, the pre-fix commit is a free mutation test.

## 7. Test the tests (mutation discipline)

- Put the bug back — **in the awkward place**, not the easy spelling — and watch the check go
  red. A gate that can only see the easy spelling reads green on the hard one.
- Confirm the mutation actually applied (a `sed` that matched nothing looks exactly like a
  test with no teeth). Clear bytecode caches between mutations.
- Strip comments before substring checks: tests have passed on their own explanatory comment,
  and on an inert directive in the wrong config section. Parse structure (AST, CSS selector
  lists, INI sections) instead of grepping text.
- **Commit before you mutate**; restore with `git checkout -- <path>`, never a blind
  `git reset --hard HEAD~1` (an empty commit makes it eat the previous one).
- Watch the test-file count: a new file with an existing name overwrote a test, and a gate
  cannot fail on a test that no longer exists.

## 8. Fixture rules

- **A fixture that makes both branches identical cannot test the branch.** Same value in
  both source tables → a precedence change is invisible. Distinct names AND distinct scores →
  the tie-breaker you claim to pin is never exercised.
- **A test that iterates a list cannot see the list shrink.** Name the load-bearing few
  explicitly beside the loop (`for required in ("x", "y"): check(required in declared)`).
- **Would it fail if the function body were deleted?** Never recompute the production
  expression in the test and compare it to itself. Assert hand-written values or real records.
- **Never assert a persisted store is empty after an operation** — that pins data loss as
  correct behaviour (see `decision-ledger`). Assert the store still holds what was captured
  and that the *computation* ignored it.
- **Cover negatives**: duplicate keys, missing optional table, unknown id, empty reason,
  stale revision, case/whitespace-only differences, the tenant that lacks the dataset.
- **Comparing two tables? Collapse to latest-value-per-entity first.** Raw rows double-count
  every entity on every date and flag lifecycle progression as conflict.
- **Hand-typed constants need a test against real data** (an anchor date hardcoded wrong in
  both code and stub fixture was wrong every single week).
- Fixtures differ from production on **exactly the dimension under test**; single-valued
  dimensions (one shift, one tenant, one team) hide whole classes of bug.

## 9. Static gates for code CI cannot execute

Browser code, unit files, infra config, prompts, SQL migrations: if nothing runs it, a PR can
be green with its headline feature broken. Write static invariant tests, and execute
extracted pure logic wherever a runtime exists.

- Catalogue the invariants that actually broke and gate each (examples in template §7):
  bare-wired event handlers whose first parameter is a domain object (the Event lands in it);
  `[hidden]` overridden by an author `display` rule; numeric `step` rejecting prefilled
  decimals; `required` fields real data cannot satisfy; a render that rebuilds a focused
  control's ancestor on every keystroke; every element id the JS dereferences exists in HTML.
- Techniques: strip comments; split CSS selector *lists* on commas; match class names with
  `\.name(?![\w-])`; name every container that holds a control explicitly; AST over regex
  where a parser exists.
- **Parity tests** when logic exists twice (server model + client port): one shared fixture
  set, run both, compare figure by figure; skip *loudly* when the runtime is absent and make
  CI have it.
- **Catalogues as gates**: a component registry whose test fails on an unregistered instance
  *and* on a registered entry point that no longer exists; a backlog-as-code whose test fails
  an item whose done-probe now says DONE (see `touch-ui-system`).
- **Ask the tool, not the config**: if production behaviour is "rsync/docker/the router
  decides", the test runs that tool in dry-run mode and asserts on its output.
- Real rendering is a third thing: "right-sized" is not "reachable" (a floor-compliant footer
  rendered off-screen), "value retained" is not "focus retained". Use a headless browser for
  those, and a device-check page for native touch behaviour synthetic events cannot prove.

## 10. Behaviour over byte-identity — and retiring a proof

- Byte-identity transfers behaviour without describing it; afterwards nobody can say what the
  code does. State behaviour in `fast` on synthetic fixtures at pure-function seams.
- Do not mock an orchestrator with eight I/O entry points — extract the pure core and test that.
- **Retiring an equivalence/migration test** (template §9):
  1. classify each of its assertions: comparison, or invariant?
  2. lift the invariants into fast synthetic tests *before* moving it;
  3. list the code paths left with no guard in a tracked issue and in the README;
  4. keep the proof runnable — retiring is not deleting;
  5. forbid putting it back in front of a release to cover a gap: write the missing behaviour test.

## 11. Claims about real data

- **"No behaviour change" is a claim about real data**, not about a green gate. Run the
  changed computation at base and head on the same real dataset, diff **per record**, and
  name the dataset and date in the PR body. Aggregates that match while records move is the
  exact shape this catches.
- Establish determinism first (base vs base). Scope the claim by the code changed, not by the
  one tenant you happened to open.
- Totals cannot see per-key loss: compare key by key against an independent witness.
- After merging two green branches, run main's newer tests on the merged tree; they can fail
  only together.

## 12. Special cases

- **Optimizers / search with no oracle**: brute-force small instances and require the search
  to reach the exhaustive optimum; give every hard rule a fixture built to break it; assert
  internal invariants (parts add up to the headline); report a ceiling no answer may exceed;
  report the spread across seeds instead of promising one number.
- **Performance**: assert **work counts** (reads, parses, solver calls), not milliseconds;
  size the fixture so the old code fails the ratio. Benchmark at production duty cycle and
  contention, warm, on the real machine — one cold sample on a VM is not a measurement.
- **Caches**: test that the cache key covers everything read (intercept file opens and assert
  the read-set), and that cached values are immutable (a mutated cached set inverted a gate).

## 13. Gate signal hygiene

- Never pipe a gate into `tail`/`head`; the pipeline reports the last command's status.
  Never chain anything after the command whose exit code you will report (`; echo $?` reports
  echo's 0). Redirect to a file and read the file.
- Quote the gate's own final line, not a count remembered from prose.
- A `preflight --suite <name>` that checks the environment *before* the gate saves a ten-minute
  run that was always going to fail.
- A known-false signal gets fixed, never memorised: a permanently red warning trains people to
  ignore red.

---

## Translation: FastAPI · React/TS · Postgres · LangGraph/MCP · Docker · GitHub Actions

| Concept | Reference stack | Your stack |
|---|---|---|
| Check-collecting standalone tests | `python tests/test_x.py` with `check()` | pytest is fine: one behaviour per module, incident docstring, avoid `-x` in the gate |
| Suite registry, fail closed | tuples in `scripts/suites.py` | pytest markers + a `conftest.py` collection hook that errors when a test touching private data/real services is unmarked (template §10) |
| Runner outcomes | custom runner, exit 1/2/3 | wrap pytest: exit 2/3 (interrupted/internal) and negative codes → "no verdict"; treat exit 5 (no tests collected) as failure |
| Network off | dead-proxy env | `pytest-socket --disable-socket`, `respx`/`responses`; keep the proxy trick for subprocesses |
| Database | files on disk | Postgres via `testcontainers` or a compose service; transaction-per-test with rollback; seeded synthetic data (`synthetic-world`) |
| Fails-at-base | `git archive` + overlay | same script, runs `pytest <file>`; a CI job can run it for PRs labelled `bugfix` |
| Static gates for UI | Python regex over JS/CSS | ESLint/stylelint custom rules (e.g. forbid arbitrary `text-[13px]`, raw hex colours), TS strict; vitest for pure logic; Playwright for real-rendering truths |
| Parity tests | node runs the JS port vs Python | shared JSON fixtures read by both pytest and vitest |
| Acceptance | private real data on a trusted machine | for a synthetic-data project: golden scenarios on the seeded world **plus LLM evals** (expected tool + asserted values + refusal cases); can run in CI |
| Release gate | `run_gate.sh` = fast + acceptance | a required GitHub Actions job; deploy job `needs:` it and records the result in provenance (`release-provenance`) |

## Checklists

**Before opening a PR**
- [ ] Every claimed fix has a test that fails at the merge base on the assertion naming the bug (quote it in the body).
- [ ] Each fixture differs between old and new behaviour on the dimension under test.
- [ ] The test would fail if the guarded thing were removed; load-bearing list items named explicitly.
- [ ] Private-data tests registered in `acceptance`; fast tests run from a clean checkout.
- [ ] UI/config changes have a static gate (or an executed extract); mutation-checked in the awkward place.
- [ ] "No behaviour change" backed by a per-record diff on named real data.

**Reviewing a test**
- [ ] Run it at base yourself; `SETUP FAILED`/no marker is inconclusive, not a pass.
- [ ] Look for: comment-satisfied checks, early returns, unguarded `next()`, recomputed production expressions, empty-store assertions, iterate-only list checks.

## Anti-patterns (each shipped somewhere and looked correct)

- A hand-maintained test chain that silently dropped files → discover by glob + fail-closed registry.
- A string-matched exclude list instead of asking the transfer tool → a whole module stopped shipping.
- Re-adding a migration proof "to be safe" → it hides that behaviour is unspecified.
- `grep -l x && grep -q y || echo OK` → prints OK for exactly the violating case; use explicit if/then/else.
- A detection command that prints a wrong number in an authoritative format → worse than no command; delete it.
- A suite-wide check with an allowlist → an allowlisted gate is a disabled gate; scope checks to the diff instead.

## Related skills
`agentic-workbench` (reviewer protocol that runs these checks) · `release-provenance` (gate
status recorded on deploy) · `touch-ui-system` (static UI gates, registry, backlog-as-code) ·
`legacy-port-migration` (equivalence → invariants) · `synthetic-world` (fixtures and seeded data).
