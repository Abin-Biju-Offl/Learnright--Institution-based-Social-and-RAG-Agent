# engineering-journal — templates

## LOG.md header

```markdown
# LOG — learnings, reviews, and status history (append-only)

What the system IS: SPEC.md. Why: design.md. Current status: README.md.
Entries are never rewritten; corrections are new text that says what they correct.

## Learnings log
<entries>

## Reviews log
<dated design-gate verdicts + must-fix lists>

## Status history
<one line per milestone>
```

## Journal entry

```markdown
### 2026-03-18 — a refusal must never cost the user their typed work

> "It keeps telling me to reload before I can save." — the most common complaint from the floor.

**Trigger.** <who reported what, when>.

**Mechanism (measured).** The precondition hashed whole files; a capture rewrote them every
minute (hundreds of runs a morning), so a 10-minute edit almost always collided. The refusal advised
reloading — the one action that discards the edits.

**Fix.** Preconditions scoped to the rows the save owns (`write_scope.rows`), per-subject
tokens returned on 409, client replays edits onto fresh rows (`conflict.reapply`).
Server messages state facts only.

**The rule.** A refusal names the subject, keeps the user's work, and is counted.

**Not done.** Auto-save of a merged result — deliberately: the user re-approves what they see.

**Tests.** `tests/test_refusal_keeps_edits.py` (fails at `abc1234` with "FAIL an untouched
row keeps the typed value"); `tests/test_stale_message_never_says_reload.py`.

**Gate.** 142 fast + 12 acceptance.
```

## Status-history line

```markdown
- **2026-03-18 (refusals)** — preconditions per row/subject; refusal log; edits replayed after a 409. 2 tests fail at base. Gate 142+12. Deployed <sha> → <host>. Next: measure refusal rate for a week.
```

## README "Current status" item

```markdown
**Saves no longer collide across lines (2026-03-18).** Two editors on different lines both
land (was: second refused 100% of the time while the capture ran); a clash on the same row
is refused by name and the editor's typed values are replayed onto the fresh rows. Refusals
are logged (`save-refused`), 31 in the first day vs ~200/day before.
**Next: deploy to <tenant> and confirm the refusal rate stays under 5/day.**
```

## Decision record

```markdown
## 7. Narrow the scheduler instead of widening its rule set (2026-02-02)

### The problem
The scheduler hardcoded one tenant's locality cascade and priority tiers; the second tenant
needed ~10 more rules. A strategy per rule does not scale.

### The decision
The engine only fills genuine holes, scored by closeness to the vacated person's target.
Scoping (zones, floors) moves to the caller, which partitions and calls the same engine
once per scope.

### Alternatives considered and rejected
| Option | Why rejected |
|---|---|
| A named strategy per tenant rule | the registry grows per tenant; complexity accretes |
| Global optimization | moves ~10× more people for marginal gain; a different skill |

### Deliberately not changed
The forecast inside the scheduler (separate concern, has its own inputs).

### Open questions
How do capacity-reduction directives persist — durable rows or per-run flags?

### Impact on tests
Byte-identity replaced by invariants; accepted divergences reported (never failed) with counts.
```

## Plan document skeleton

```markdown
# <Feature> — implementation plan
**Status:** <one line> · **Last updated:** <date> · **Current slice:** <n>
**Goal:** <what users can do afterwards>

This is the resumable plan. Update status, checkboxes, decisions and "Resume here" at the
end of each session. Code milestones also update README Status/Next and LOG.md.

## 1. Delivery decision
### v1 simplicity rules
- No database. - No new frontend framework. - No generic table editor.
- No arbitrary-row write endpoint. - No reimplementation of server logic in the browser.

## 2. Slice 1 — <name>
### Scope  - [ ] item  - [x] item
### Deliberate caveats
### Exit criteria  - [ ] <a real user does X without Y>  - [x] existing tests stay green
### Tests owed

## N. What shipped, and what the build changed about this spec
1. <correction reality forced, and why>

## Baseline snapshot (<dataset>, as of <date>) — scoped claims for regression fixtures
- <count> <thing> in <scope>; <count> of them <property>.

## Resume here
<the very next action>
```

## Incident note

```markdown
# "<the error message the user saw>"
## The problem — what the user experienced, when, how often
## Root cause — the mechanism, with evidence
## What we fixed — code + tests + config
## If someone still sees it — what to check, in order; who to tell
```

## `.gitattributes` for a single-file append-only log

```
LOG.md merge=union
```
Union merge keeps both branches' added lines. Review the merged order after big merges.

## A tiny test that keeps the convention honest

```python
import re
from pathlib import Path

log = Path("LOG.md").read_text(encoding="utf-8")
heads = re.findall(r"^### (\d{4}-\d{2}-\d{2})\b", log, re.M)
check(heads == sorted(heads), "entries are appended in date order (append-only: never edited,\n"
      "never inserted above older ones — which also makes `merge=union` behave)")
for h in re.findall(r"^### \d{4}-\d{2}-\d{2}.*$", log, re.M):
    check(" — " in h, f"entry heading states the lesson after an em dash: {h[:60]}")
```
