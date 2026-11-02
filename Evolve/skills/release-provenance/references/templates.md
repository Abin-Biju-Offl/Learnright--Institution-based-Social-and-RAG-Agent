# release-provenance — templates

## §1 Production wrapper (bash)

```bash
#!/usr/bin/env bash
# deploy/deploy.sh --scope <tenant> --host <host> [--yes] [--skip-tests] [--break-glass "reason"]
set -euo pipefail
scope=""; host=""; yes=0; skip=0; reason=""
while [ $# -gt 0 ]; do case "$1" in
  --scope) scope="$2"; shift 2;; --host) host="$2"; shift 2;; --yes) yes=1; shift;;
  --skip-tests) skip=1; shift;; --break-glass) reason="$2"; shift 2;;
  *) echo "unknown flag $1" >&2; exit 2;; esac; done
[ -n "$scope" ] && [ -n "$host" ] || { echo "need --scope and --host" >&2; exit 2; }

# 1. Validate EVERYTHING before the first mutation
channel=production
if [ -n "$reason" ]; then
  [[ "$reason" =~ ^[A-Za-z0-9][A-Za-z0-9\ ._:/#-]{7,159}$ ]] || { echo "break-glass reason must be 8-160 safe characters" >&2; exit 2; }
  [ "$skip" -eq 0 ] || { echo "break-glass never skips the gate" >&2; exit 2; }
  channel=emergency
fi
[ -z "$(git status --porcelain --untracked-files=normal)" ] || { echo "dirty tree: commit or stash first" >&2; exit 1; }
git fetch --quiet origin
sha="$(git rev-parse HEAD)"; tree="$(git rev-parse 'HEAD^{tree}')"
if git merge-base --is-ancestor "$sha" origin/main; then
  [ "$channel" = production ] || { echo "already released: break-glass is unnecessary" >&2; exit 1; }
else
  [ "$channel" = emergency ] || { echo "STOP: $sha is not on origin/main" >&2; exit 1; }
fi
env_source="$(resolve_env_source "$scope")"          # secret version pinned NOW; fail fast
[[ "$env_source" =~ ^(file:[A-Za-z0-9._/-]+|secret:[a-z0-9-]+#[0-9]+)$ ]] || { echo "bad env source" >&2; exit 2; }

# 2. Consent
if [ "$yes" -eq 0 ]; then
  read -r -p "Deploy $sha ($channel) to $host? Type the host name: " typed
  [ "$typed" = "$host" ] || { echo "aborted" >&2; exit 1; }
fi

# 3. Gate (recorded either way)
if [ "$skip" -eq 1 ]; then gate=skipped; else scripts/run_gate.sh .venv/bin/python; gate=passed; fi

# 4. Artifact from the commit — never the working tree
art="$(mktemp -d)"; trap 'rm -rf "$art"' EXIT
git archive "$sha" | tar -x -C "$art"
chmod 0755 "$art"
source deploy/excludes.sh                            # SHIP_EXCLUDES
rsync -az --delete "${SHIP_EXCLUDES[@]}" --rsync-path="sudo rsync" "$art/" "$host:/opt/app/"
write_manifest "$host" transferred                      # phase 1: bytes landed
ssh "$host" "sudo chown -R root:app /opt/app && sudo chmod -R u=rwX,g=rX,o= /opt/app"   # code is read-only to the service

# 5. Render config, restart, health (bounded retries), phase 2
render_and_install_env "$host" "$scope" "$env_source"
ssh "$host" "sudo systemctl restart app-web app-worker"
for i in $(seq 1 15); do
  if ssh "$host" "curl -fsS http://127.0.0.1:8080/healthz >/dev/null"; then
    write_manifest "$host" healthy; echo "SHIPPED $sha to $host"; exit 0
  fi
  sleep 2
done
write_manifest "$host" unhealthy
echo "SHIPPED, RUNTIME UNVERIFIED: health never answered on $host" >&2
exit 1
```

```bash
write_manifest() {   # host phase — atomic, one writer, no secrets
  local host="$1" phase="$2"
  ssh "$host" "sudo install -d -m 0750 /etc/app && sudo tee /etc/app/release.env.tmp >/dev/null && sudo chmod 0644 /etc/app/release.env.tmp && sudo mv /etc/app/release.env.tmp /etc/app/release.env" <<EOF
RELEASE_COMMIT=$sha
RELEASE_TREE=$tree
RELEASE_SCOPE=$scope
RELEASE_CHANNEL=$channel
RELEASE_GATE=$gate
RELEASE_CONFIG_SOURCE=$env_source
RELEASE_EMERGENCY_REASON=$reason
RELEASE_PHASE=$phase
RELEASED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
}
```

## §2 Fleet reader (read-only)

```python
#!/usr/bin/env python3
"""fleet_check.py — what is each host ACTUALLY running? Exit 0 all current+live · 1 drift · 2 unreachable."""
import subprocess, sys

HOSTS = {"tenant-a": "app-a", "tenant-b": "app-b"}           # from config, not hardcoded in practice
UNITS = ("app-web", "app-worker")
# /etc/app is 0750 root (it also holds the secrets file): a sudoers rule allows exactly this read.
PROBE = ("sudo -n cat /etc/app/release.env; echo ---; systemctl is-active " + " ".join(UNITS) +
         "; echo ---; cat /srv/app-data/{tenant}/canonical/_provenance.json 2>/dev/null || true")


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True)


def classify(sha: str) -> str:
    if not sha:
        return "no-record"
    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode:
        return "unknown-commit"
    if git("merge-base", "--is-ancestor", sha, "origin/main").returncode:
        return "not-on-main"
    behind = int(git("rev-list", "--count", f"{sha}..origin/main").stdout.strip() or 0)
    return "current" if behind == 0 else f"behind {behind} (rollback or unpulled?)"


worst = 0
for tenant, host in HOSTS.items():
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", host, PROBE.format(tenant=tenant)],
                           capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"{tenant}: UNREACHABLE (timeout)"); worst = 2; continue
    if r.returncode not in (0, 3):                            # is-active exits 3 when inactive
        print(f"{tenant}: UNREACHABLE"); worst = 2; continue
    manifest_txt, active_txt, data_txt = (r.stdout.split("---\n") + ["", "", ""])[:3]
    m = dict(l.split("=", 1) for l in manifest_txt.splitlines() if "=" in l)
    state = classify(m.get("RELEASE_COMMIT", ""))
    concerns = []
    if m.get("RELEASE_CHANNEL", "production") != "production": concerns.append(f"channel={m['RELEASE_CHANNEL']}")
    if m.get("RELEASE_GATE") != "passed": concerns.append(f"gate={m.get('RELEASE_GATE')}")
    if m.get("RELEASE_PHASE") != "healthy": concerns.append(f"phase={m.get('RELEASE_PHASE')}")
    if m.get("RELEASE_SCOPE") not in (None, tenant): concerns.append(f"scope={m['RELEASE_SCOPE']}")
    states = active_txt.split()
    if len(states) != len(UNITS) or any(s != "active" for s in states):   # empty output is NOT active
        concerns.append(f"runtime NOT active now ({' '.join(states) or 'no answer'})")
    if not data_txt.strip():
        concerns.append("no data provenance marker")                   # unknown is never current
    print(f"{tenant}: {state}" + (f" — {', '.join(concerns)}" if concerns else ""))
    if state != "current" or concerns:
        worst = max(worst, 1)
sys.exit(worst)
```

## §3 GitHub Actions + Cloud Run translation

```yaml
# .github/workflows/release.yml
name: release
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write                      # keyless auth to the cloud (workload identity federation)
env:
  IMAGE: europe-docker.pkg.dev/my-project/app/api
jobs:
  fast:
    uses: ./.github/workflows/ci.yml   # the same fast suite PRs run
  acceptance:
    needs: fast
    runs-on: ubuntu-latest             # synthetic-world data: runs in CI; real data: a trusted runner
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -c constraints.txt
      - run: python scripts/run_suite.py acceptance --keep-going
  build:
    needs: [fast, acceptance]          # gate=passed below is true only because of this line
    runs-on: ubuntu-latest
    outputs:
      digest: ${{ steps.push.outputs.digest }}
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.WIF_PROVIDER }}
          service_account: ${{ vars.DEPLOY_SA }}
      - uses: google-github-actions/setup-gcloud@v2
      - id: push
        run: |
          gcloud auth configure-docker europe-docker.pkg.dev --quiet
          docker build --label org.opencontainers.image.revision="$GITHUB_SHA" -t "$IMAGE:sha-${GITHUB_SHA::7}" .
          docker push "$IMAGE:sha-${GITHUB_SHA::7}"
          echo "digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE:sha-${GITHUB_SHA::7}")" >> "$GITHUB_OUTPUT"
  deploy-tenant-a:
    needs: build
    environment: tenant-a              # required reviewers = per-target consent
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.WIF_PROVIDER }}
          service_account: ${{ vars.DEPLOY_SA }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud run deploy app-tenant-a --region europe-west1 \
            --image "${{ needs.build.outputs.digest }}" --no-allow-unauthenticated \
            --update-labels "commit=${GITHUB_SHA::12},channel=production,gate=passed"
          python scripts/record_release.py --target tenant-a --phase transferred
          if ./scripts/wait_healthy.sh app-tenant-a; then
            python scripts/record_release.py --target tenant-a --phase healthy
          else
            python scripts/record_release.py --target tenant-a --phase unhealthy; exit 1
          fi
```
Revision labels hold the **immutable** facts (commit, channel, gate). The **phase** changes
after the health check, so record it somewhere that doesn't create a new revision — a
`releases` table, or GitHub's Deployments API — rather than relabelling the service, which can
roll a new revision that was never health-checked.

## §4 Testing the wrapper with fake tools

```python
import os, subprocess, tempfile
from pathlib import Path

FAKE = """#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$FAKE_LOG"
"""


def fake_bin(tmp: Path, tools=("rsync", "ssh", "gcloud", "systemctl")) -> Path:
    b = tmp / "bin"; b.mkdir()
    for t in tools:
        p = b / t; p.write_text(FAKE); p.chmod(0o755)
    return b


def test_unmerged_commit_is_refused_and_nothing_moves():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        repo = make_repo_with_release_line(tmp)          # origin/main + an unmerged branch checked out
        log = tmp / "calls.log"
        env = {**os.environ, "PATH": f"{fake_bin(tmp)}:{os.environ['PATH']}", "FAKE_LOG": str(log)}
        r = subprocess.run(["bash", "deploy/deploy.sh", "--scope", "t1", "--host", "h", "--yes", "--skip-tests"],
                           cwd=repo, env=env, capture_output=True, text=True)
        check(r.returncode != 0, "an unmerged commit is refused")
        check("not on origin/main" in r.stderr, "the refusal names the reason")
        check(not log.exists() or "rsync" not in log.read_text(), "no bytes were transferred")
```
