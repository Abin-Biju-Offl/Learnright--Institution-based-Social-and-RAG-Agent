# Operations agents — skeletons

## §1 The procedure skill (`.claude/skills/deploy/SKILL.md`)

```markdown
---
name: deploy
description: Deploy the merged main line to the tenant hosts — fleet status, full gate, one host at a time with explicit per-host human consent, then read provenance back and verify the runtime. Use for "deploy", "deploy <tenant>", "what's deployed where".
---
This skill IS the runbook procedure with the values filled in. Your first tool call is step 0.

0. Prove you are in the PRIMARY checkout on main:
   `test "$(git rev-parse --git-common-dir)" = "$(git rev-parse --git-dir)"` and
   `git switch main && git pull --ff-only`. A linked worktree or feature branch → STOP.
1. `scripts/fleet_check.py` (read-only). Any of: not-on-main, gate-not-passed, runtime
   inactive, scope mismatch → STOP and hand back to the human with the output.
2. Ask: "Deploy <host> to <sha>? (yes/no)". Consent is per host, in THIS conversation;
   a yes for one host never covers another.
3. Launch ONE `deploy-operator` agent for that host. Wait for its report.
4. Repeat 2–3 per host, sequentially.

| Situation | Action |
|---|---|
| gate red / killed | stop; KILLED → re-run once, then hand back |
| a host reports RUNTIME UNVERIFIED | stop the sequence; hand back |
| anything needing rollback or break-glass | human runbook only — do not attempt |
```

## §2 The single-target executor (`.claude/agents/deploy-operator.md`)

```markdown
---
name: deploy-operator
description: Deploys ONE host by the runbook. Requires that a human already said yes to this specific host in this conversation.
tools: Bash, Read, Grep, Glob
model: opus
---
## Never
- Deploy without a per-host yes in this conversation.
- Use --skip-tests, a development channel, or break-glass.
- Move data in either direction. Edit the host's config by hand.
- Invent a flag or a state-changing remote command. A missing capability is a PR, not an improvisation.
- Put anything after the wrapper on its line (no `| tail`, no `; echo $?`, no `&&`).

## Do
1. `deploy/<tenant>.sh --yes > /tmp/deploy-<tenant>.log 2>&1` — then read the log; the exit
   code is in the log's last lines / the wrapper's own summary.
2. Read back the provenance record on the host (commit, tree, channel, gate status, phase, time).
3. Check the live runtime (`systemctl is-active <units>` / health endpoint) — the record is a
   claim made at deploy time; this is the fact now.

## Report (exactly one)
SHIPPED · SHIPPED, RUNTIME UNVERIFIED · NOT SHIPPED · ESCALATE TO HUMAN
with: commit, provenance excerpt, runtime state, log tail. Never SHIPPED on an exit code alone.
```

## §3 Failure-modes catalogue entry (consulted when something is off)

```markdown
## F<n>. <Symptom as the operator sees it> — <BLOCKER | WARN>
**Why it happens:** <mechanism>.
**Detect:** `<read-only command>` → <what a bad result looks like>
**Do:** <the safe next step>. **Never:** <the tempting wrong fix>.
**Origin:** <date, one sentence>.
```

Examples worth having on day one: "deploy log looks clean but the wrapper failed" (a pipe or
trailing command masked the exit code); "deployed but the service is not running"; "the
record says commit X but the host serves Y" (someone synced by hand); "a config change
deployed but did nothing" (code-only sync path doesn't re-render config).

## §4 Pinning the procedure with tests

```python
import re
from pathlib import Path

for doc in (".claude/skills/deploy/SKILL.md", ".claude/agents/deploy-operator.md"):
    text = Path(doc).read_text(encoding="utf-8")
    # only the COMMANDS (inside backticks) — prose lines about the rule must not trip the check
    for cmd in re.findall(r"`([^`]*deploy/[\w.-]+\.sh[^`]*)`", text):
        after = cmd.split(".sh", 1)[1]
        after = re.sub(r"\s*[12]?>\s*\S+", "", after)       # redirections are allowed
        after = after.replace("2>&1", "")
        check(not re.search(r"[|;&]", after), f"{doc}: nothing may follow the wrapper: {cmd}")
    for target in re.findall(r"\]\(([^)#]+)\)", text):
        check((Path(doc).parent / target).exists() or Path(target).exists(),
              f"{doc}: link resolves -> {target}")
```

And a recording fake `ssh` on `PATH` proving the read-only fleet reader never issues a
mutating verb (`rsync`, `restart`, `rm`, `tee`, `chown`, `>`).
