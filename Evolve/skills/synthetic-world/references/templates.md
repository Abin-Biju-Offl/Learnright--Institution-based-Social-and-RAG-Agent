# synthetic-world — templates

## §1 Blueprint

```yaml
# blueprints/small-site.yaml
id: small-site
version: 3
seed: 7
seed_date: "2026-03-13"            # quoted: unquoted YAML dates load as date objects
days: 7
calendar: { closed_weekdays: [Sun] }
units: { count: 18, stations_per_unit: [10, 16] }
people:
  count: 1200
  roles: { operator: 0.85, helper: 0.10, checker: 0.05 }
  attendance_rate: { mean: 0.93, sd: 0.04 }
skills:
  catalogue: 40
  per_person: [2, 6]
  rating_pct: { mean: 78, sd: 15, min: 20, max: 140 }
rotation: { teams: [A, B], swap: weekly, anchor: "2026-03-09" }
anomalies:
  duplicate_header: [ratings]
  id_change: 3
  same_name_pairs: 2
  missing_optional: [sensor_readings]
  dropped_from_snapshot_while_active: 2
```

## §2 Generator skeleton (deterministic per entity)

```python
import csv, hashlib, json, random
from datetime import date, timedelta
from pathlib import Path


def rng(seed: int, *stream: object) -> random.Random:
    """Independent stream per entity: adding one more person changes nobody else's values."""
    return random.Random(hashlib.sha256(f"{seed}:{':'.join(map(str, stream))}".encode()).hexdigest())


def people(bp) -> list[dict]:
    out = []
    for i in range(bp["people"]["count"]):
        r = rng(bp["seed"], "person", i)
        out.append({"person_id": f"P{i:05d}", "name": neutral_name(r),
                    "home_unit": str(r.randrange(bp["units"]["count"]) + 1),
                    "attendance_rate": min(0.995, max(0.6, r.gauss(0.93, 0.04)))})
    return out


def attendance(bp, roster) -> list[dict]:
    rows, start = [], date.fromisoformat(bp["seed_date"]) - timedelta(days=bp["days"] - 1)
    for d in range(bp["days"]):
        day = start + timedelta(days=d)
        if day.strftime("%a") in bp["calendar"]["closed_weekdays"]:
            continue                                         # absent means missing
        for p in roster:
            if rng(bp["seed"], "presence", day.isoformat(), p["person_id"]).random() < p["attendance_rate"]:
                rows.append({"date": day.isoformat(), "person_id": p["person_id"], "status": "present"})
    return sorted(rows, key=lambda r: (r["date"], r["person_id"]))   # total order


def write_csv(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    return len(rows)
```

## §3 Provenance writer

```python
def write_pack(out: Path, bp: dict, tables: dict[str, tuple[str, int, str]]) -> None:
    pack = {
        "blueprint": f"{bp['id']}@{bp['version']}", "generator_version": GENERATOR_VERSION,
        "code_digest": code_digest(Path(__file__).parent),
        "run_id": "run_" + hashlib.sha256(json.dumps(bp, sort_keys=True).encode()).hexdigest()[:12],
        "rng_seed": bp["seed"], "seed_date": bp["seed_date"], "declared_world": True,
        "tables": {name: {"origin": origin, "rows": n, **({"note": note} if note else {})}
                   for name, (origin, n, note) in sorted(tables.items())},
        "anomalies": sorted(f"{k}:{v}" for k, v in bp.get("anomalies", {}).items()),
        "absence_semantics": "absent means missing: a person who did not attend has no row",
    }
    (out / "_pack.json").write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n")
    # no timestamps inside the pack: regeneration must be byte-identical
```

## §4 Determinism test

```python
import hashlib, os, subprocess, sys, tempfile
from pathlib import Path


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


hashes = set()
for seed_env, tz in (("0", "UTC"), ("1", "America/Los_Angeles")):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([sys.executable, "-m", "world.generate", "blueprints/small-site.yaml", d],
                       env={**os.environ, "PYTHONHASHSEED": seed_env, "TZ": tz}, check=True)
        hashes.add(tree_hash(Path(d)))
check(len(hashes) == 1, "regeneration is byte-identical across hash seeds and time zones")
```

## §5 Scenario definition

```yaml
# scenarios/two_absent_on_unit_1.yaml
id: two_absent_on_unit_1
base: small-site@3
date: "2026-03-12"
mutations:
  - mark_absent: [P00017, P00342]          # both seated on unit 1
expect:
  planner: { unit: "1", holes_filled: ">= 1", throughput_drop_vs_naive: "< 15%" }
  agent_eval: { question: "Unit 1 is short two people — what should I do?",
                expect_tool: propose_assignment, expect_args: { unit_id: "1" } }
  manual: "Mark both absent in the UI; the plan shows two holes and a proposal; nothing auto-applies."
```

## §6 compose: seed the database once

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_PASSWORD: dev-only-placeholder }
    volumes: [db:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 10
  seed:
    build: .
    command: ["python", "-m", "world.load", "--if-empty"]    # COPY the canonical CSVs; no-op if loaded
    depends_on:
      db:
        condition: service_healthy
volumes: { db: {} }
```
