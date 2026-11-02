# Rules files — skeletons

## §1 `CLAUDE.md` (root rules for coding agents)

Keep it under ~250 lines. Order matters: models first, then rules, then pointers.

```markdown
# Working in this repo — agent instructions

Procedures: `deploy/RUNBOOK.md`. State: `README.md` (Status/Next) and `LOG.md` (journal).
Contract: `SPEC.md`. This file is the contract you must not break; most of it is invisible
until you touch a data path, a new file type, or the deploy layer.

## The one mental model: two truths
- **Code** — source of truth is git. Production receives an artifact built from a commit
  on the release line, never the working tree.
- **Data** — source of truth is the running instance (or the database). It flows UP to
  backups routinely and DOWN only for first-time setup or recovery.

## The third axis: product vs workbench
Would production at 3am be worse off without this file? No → workbench: it is excluded
from the deploy artifact (see `<exclude list>`), and `tests/test_ship_boundary.py`
pins it. The product agent's instructions live in `<app>/agent/prompt.py`, nowhere else.

## Rules (do not violate)
1. **Never commit data.** <data trees> are ignored on purpose. Don't add data "to make a test pass".
2. **New generated artifact → BOTH lists**: `.gitignore` and `<deploy exclude list>`. They move in lockstep.
3. **No secrets in the tree.** Production secrets live in <secret store>; dev uses `.env` (ignored). New knobs go in `.env.example`, documented.
4. **Production owns live data.** No feature or script pushes data down onto a running instance as a routine step.
5. **New runtime-writable path → sandbox grant** (`ReadWritePaths=` / volume mount). Ungranted writes fail silently.
6. **Adding a tenant = the scaffold**: `scripts/scaffold_tenant.py <id> --apply`, then `--check`. Per-tenant behaviour lives in the manifest, never in `if tenant == "x"` in core.
7. **Never delete information.** Anything captured may be excluded from a computation but never erased. "Off" stops *reading*; a decision to stop applying is recorded as a row/flag, never as an absence. A test asserting a store is empty after an operation is asserting data loss.
8. **Development is not production.** Production deploys only commits reachable from `origin/main`; one named break-glass path exists (RUNBOOK §x).

## Domain authority
Before writing any detector or any code comparing two descriptions of the same thing, read
`docs/decision-authority.md`. Report contradictions and genuine absences — never a
difference a human chose.

## UI
Before touching the frontend read `docs/ui-language.md` and search the component registry
(`<app>/ui/registry.py`) before building anything interactive. What to work on next:
`python -m <app>.ui.backlog` (code, not prose).

## Repo conventions
- Gate: `scripts/run_gate.sh` (fast + acceptance) must pass before a deploy.
- Commit per coherent milestone, updating `LOG.md` (entry + status line) and README Status/Next **in the same commit**.
- Suites answer different questions (fast / acceptance / archived); the archived migration proof is in no gate.
- Git flow: issue → branch → PR → CI fast → review → merge → full gate → deploy.

## Before you open a PR
- Read `.claude/review/hard-rules.md` and `docs/writing-tests.md`.
- Run your new test at the merge base: `scripts/prove-fails-at-base.sh "$(git merge-base origin/main HEAD)" tests/test_x.py` — it must fail on the assertion naming the bug.
- Write the body as falsifiable claims with numbers. "No behaviour change" names the dataset/date you diffed per record.
- When revising after review, the prose is part of the diff: re-read the body, grep for renamed/deleted names, run `scripts/check_prose_refs.py "$(git merge-base origin/main HEAD)"`.

## Concurrent sessions
Start any code-writing task in its own worktree; leave it with keep/remove. One task, one worktree.
```

## §2 `AGENTS.md` (pointer for other agents)

```markdown
# Agent instructions (Codex & others)
The full guidance is in CLAUDE.md — read it. Non-negotiables, short form:
1. Two truths: code from git (artifact on deploy); data owned by production (flows up only).
2. Never commit data. 3. New generated artifact → .gitignore AND the deploy exclude list.
4. No secrets in the tree; new knobs in .env.example. 5. New runtime-writable path → sandbox grant.
6. New tenant → scaffold + --check. 7. Gate before deploy: scripts/run_gate.sh.
```

## §3 `.claude/review/hard-rules.md` (detection checklist)

```markdown
# Hard rules — the regression checklist

Every rule here has been broken at least once and each break shipped looking correct.
This file is how a reviewer DETECTS the break; CLAUDE.md says why the rule exists.

Grades: BLOCKER = do not merge · MUST-FIX = fix on this branch first · ASK = a human
decides · CONSIDER = judgement (rule 0 only).

    BASE=$(git merge-base origin/main HEAD)   # the fork point, not origin/main
    DIFF="git diff $BASE...HEAD"              # three dots, always

## 0. Simple is beautiful — CONSIDER, escalating to ASK
Can the PR body say, in one sentence, what problem goes away?
### Detect
    git diff --shortstat $BASE...HEAD             # the whole change
    git diff --stat $BASE...HEAD -- "$FILE"       # vs the hunk that fixes the named problem
### Report
An abstraction with one implementation · configurability nobody asked for · a new concept
where an existing one fits · a rewrite smuggled inside a fix. Say so when a PR deletes more
than it adds and still solves the problem.
### Do NOT report
Structure the architecture mandates · effort · a badly written body (that is a body
finding) · style. If you cannot name the simpler thing, you have no finding.

## 2. A new generated artifact goes in BOTH lists — BLOCKER
### Detect
    $DIFF -- .gitignore <deploy-exclude-file>
    # every new runtime write target the diff introduces:
    $DIFF -- '*.py' | grep -nE '^\+.*(write_text|to_csv|json\.dump|open\(.*["'\'']w)'
For each new path: inside an existing ignored tree, or added to both lists?

## 6. Never delete information — BLOCKER
### Detect (a net, not a proof — (d) does the work)
    # (a) empty container written over a store
    $DIFF -- '*.py' | grep -nE '^\+' | grep -E '(write_text|json\.dump|to_csv)\s*\(.*(\[\]|\{\})'
    # (b) outright destruction
    $DIFF -- '*.py' | grep -nE '^\+.*(\.unlink\(|rmtree|os\.remove|truncate\()'
    # (c) a test pinning data loss
    $DIFF -- 'tests/*.py' | grep -nE '^\+.*(len\(.*\)\s*==\s*0|==\s*\[\]).*(store|log|override)'
    # (d) READ every write path the diff introduces and ask what the store held before
### Report
A write that persists an empty container over an existing store; a test asserting a store
is empty after an operation.

## 8. Test classification — MUST-FIX
### Detect (explicit if/then/else — `a && b || echo OK` prints OK for the violation)
    for t in $(git diff --name-only --diff-filter=A $BASE...HEAD -- 'tests/test_*.py'); do
      if grep -qE 'PRIVATE_DATA_ROOT|LEGACY_REPO' "$t"; then
        if grep -q "$t" scripts/suites.py; then echo "OK (registered): $t"
        else echo "VIOLATION — reads private data but sits in fast: $t"; fi
      else echo "OK (portable): $t"; fi
    done

## Reviewer hygiene (about your own run)
- Never `pip install` into a shared venv. Never pipe a gate into `tail`.
- Exit code last: `cmd > log 2>&1` then read the log; never `; echo $?`.
- Write probes to files; suspect your probe when it disagrees with the PR's test.
- Commit before you mutate; restore with `git checkout -- <path>`.
- Collapse to latest-value-per-entity before comparing tables.
- Check whether the repo already declares the policy before calling it a bug.
- Never merge on a green gate alone where a computation changed: diff per record.
```

## §4 Writing a new rule (the entry template)

```markdown
## N. <Rule, stated generically> — <GRADE>

**Source:** CLAUDE.md rule <k> / docs/<why>.md. **Incident:** <date, one sentence, what shipped looking correct>.

### Detect
    <command(s), each run against a passing AND a failing case before committing>

### Report
<what counts as a violation>

### Do NOT report
<the counterweight: what looks like a violation but isn't>
```
