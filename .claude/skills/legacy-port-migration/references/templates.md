# legacy-port-migration — templates

## §1 Break register (the interface spec)

| # | Capability | Customer | Symptom | Category | Resolution |
|---|---|---|---|---|---|
| 1 | planner | #2 | unit key `"B-2"` became `2` | (c) #1-ism in core | `unit_key` strategy: opaque string |
| 2 | planner | #2 | slot `S1` mapped to customer #1's code `A1` | (c) | `slot` strategy: single constant |
| 3 | forecast | #2 | efficiency missing for most rows | (a) adapter/data | crosswalk via the source's operation code |
| 4 | daily | #2 | no rotation calendar | (b) manifest value | `rotation: identity` |

## §2 Equivalence test (hermetic, explicit exclusions)

```python
"""Legacy vs new on the same pinned inputs. Lives in the ARCHIVED suite once live."""
import csv, os, subprocess, sys

from tests.offline_env import OFFLINE_ENV as OFFLINE      # ONE definition (test-gates templates §6)
ADDED_BY_NEW = {"source_run_id", "classification_flag"}     # deliberate additions, named
ACCEPTED = {                                                  # deliberate divergences, with root cause
    "capacity_per_hour": "unit changed from per-shift to per-hour (÷8), see design §8",
}

legacy = run([sys.executable, "legacy/report.py", "--date", DATE], env={**os.environ, **OFFLINE})
new = run([sys.executable, "-m", "app.report", "--date", DATE], env={**os.environ, **OFFLINE})
L, N = index(read_csv(legacy), key=("unit", "station")), index(read_csv(new), key=("unit", "station"))

only_one_side = set(L) ^ set(N)
check(not only_one_side, f"same row identities ({len(only_one_side)} rows exist on one side only)")
diverged: dict[str, int] = {}
for k in L.keys() & N.keys():
    for col in L[k].keys() - ADDED_BY_NEW:
        if L[k][col] == N[k].get(col):
            continue
        if col in ACCEPTED:
            diverged[col] = diverged.get(col, 0) + 1       # REPORTED, not failed
        else:
            check(False, f"{k} {col}: legacy {L[k][col]!r} != new {N[k].get(col)!r}")
for col, n in sorted(diverged.items()):
    print(f"ACCEPTED divergence {col}: {n} rows — {ACCEPTED[col]}")
```

## §3 Divergence proof by ratio (keeps anomalies visible)

```python
def ratio_report(rows, legacy_col, new_col, expected_ratio, tol=1e-6):
    matches, anomalies = 0, []
    for r in rows:
        lv, nv = float(r[legacy_col]), float(r[new_col])
        if nv and abs(lv / nv - expected_ratio) <= tol:
            matches += 1
        else:
            anomalies.append((r["key"], lv, nv))
    print(f"{matches}/{len(rows)} match ÷{expected_ratio}; anomalies: {anomalies[:5]}")
    return anomalies          # an unexplained anomaly is a follow-up, not a waiver
```

## §4 Parallel-run diff (cut-over evidence)

```python
for request in sample_real_requests(days=7):
    old, new = legacy_client.ask(request), new_client.ask(request)
    verdict = compare(old, new)          # identical | deliberate (named) | regression | old-wrong
    record(request.id, verdict)
summary = tally(records)                 # cut over only when regressions == 0 for N days
```

## §5 Seam checklist

- [ ] Customer #1 vocabulary moved into a manifest; engine delegates; nothing hardcoded remains.
- [ ] Contract validator written and run on both customers.
- [ ] Byte-identity proof on #1 green; reviewer gate passed; must-fix list closed.
- [ ] Least-coupled capability ported and run on #2; breaks categorised.
- [ ] Near-identity adapter for #1: one implementation per capability.
