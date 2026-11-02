# multi-tenant-platform — templates

## §1 Manifest (pure data)

```json
{
  "tenant_id": "t2",
  "display_name": "Site Two",
  "data_root_env": "T2_DATA_ROOT",
  "unit_key": {"strategy": "opaque_string"},
  "slot": {"strategy": "single", "value": "S1"},
  "rotation": {"strategy": "identity"},
  "locality": {"strategy": "none"},
  "table_layout": {"attendance": "attendance/{date}/slot-{slot}.csv"},
  "datasets": {
    "sensor_readings": {
      "path": "sensors/{date}.csv",
      "fetch": {"strategy": "cmd_template", "scope": "today_growing", "env": "T2_FETCH_CMD_SENSORS"}
    }
  },
  "semantics": {"attendance_records_absence": false, "presence_observes_location": false},
  "policy": {"max_swap_depth": 2}
}
```

## §2 Manifest schema (reject typos)

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")      # a typo is an error, not a silent default


class StrategyRef(BaseModel):
    model_config = ConfigDict(extra="allow")       # strategy params are checked by the strategy
    strategy: str


class Fetch(Strict):
    strategy: Literal["cmd_template"]
    scope: Literal["today_only", "snapshot", "today_growing", "by_id"]
    env: str


class Dataset(Strict):
    path: str
    fetch: Fetch | None = None


class Semantics(Strict):
    attendance_records_absence: bool = True        # default = the common truth
    presence_observes_location: bool = True


class Manifest(Strict):
    tenant_id: str = Field(pattern=r"^[a-z0-9-]+$")
    display_name: str
    data_root_env: str
    unit_key: StrategyRef
    slot: StrategyRef
    rotation: StrategyRef
    locality: StrategyRef = StrategyRef(strategy="none")
    table_layout: dict[str, str] = {}
    datasets: dict[str, Dataset] = {}
    semantics: Semantics = Semantics()
    policy: dict[str, int | str | bool] = {}
```

## §3 Strategy registry + profile bound once

```python
from typing import Callable, Protocol


class SlotStrategy(Protocol):
    def slots(self) -> list[str]: ...
    def normalize(self, raw: str) -> str: ...


class SingleSlot:
    def __init__(self, value: str):
        self.value = value

    def slots(self) -> list[str]:
        return [self.value]              # a degenerate constant: callers loop with no branch

    def normalize(self, raw: str) -> str:
        return self.value


REGISTRY: dict[str, Callable[..., object]] = {
    "single": SingleSlot,
    # "weekly_rotation": WeeklyRotation,   # added only when a SECOND tenant needed it
}


def make(ref: dict) -> object:
    params = dict(ref)
    name = params.pop("strategy")
    try:
        return REGISTRY[name](**params)
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}; known: {sorted(REGISTRY)}") from None


class TenantProfile:
    def __init__(self, manifest: "Manifest"):
        self.id = manifest.tenant_id
        self.slot = make(manifest.slot.model_dump())          # bound ONCE, at load
        self.datasets = manifest.datasets
        self.semantics = manifest.semantics

    def provides(self, table: str) -> bool:
        return table in self.datasets
```

## §4 Enabled-tenants gate (in code, not only in the prompt)

```python
import os
import re


class TenantNotEnabled(PermissionDenied):      # a domain error (safe-writes §6), not the builtin
    pass


TENANT_ID = re.compile(r"^[a-z0-9-]{1,32}$")


def load_profile(tenant_id: str) -> TenantProfile:
    if not TENANT_ID.match(tenant_id):                 # validate BEFORE it touches a path
        raise TenantNotEnabled("invalid tenant id")
    raw = os.environ.get("ENABLED_TENANTS")
    if raw is None and os.environ.get("APP_DEV_MODE") != "1":
        raise TenantNotEnabled("ENABLED_TENANTS is not set: refusing every tenant")   # fail closed
    enabled = {t.strip() for t in (raw or "").split(",") if t.strip()}
    if raw is not None and tenant_id not in enabled:
        raise TenantNotEnabled(f"tenant {tenant_id!r} is not enabled on this deployment")
    manifest = Manifest.model_validate_json(Path(f"tenants/{tenant_id}/manifest.json").read_text())
    return TenantProfile(manifest)
```

## §5 Capability accessor

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Availability:
    usable: bool
    fetched: bool
    message: str        # product output: shown to the user when not usable


def table_ready(profile, table: str, date: str, *, allow_fetch: bool) -> Availability:
    if not profile.provides(table):
        return Availability(False, False, f"{table} is not onboarded for {profile.id}")
    if table_has_partition(profile, table, date):
        return Availability(True, False, "")
    fetch = profile.datasets[table].fetch
    if fetch is None or not allow_fetch:
        return Availability(False, False, f"no {table} for {date}, and this host cannot fetch it")
    if fetch.scope == "today_only" and date != today().isoformat():   # str vs str, not str vs date
        return Availability(False, False, f"{table} can only be fetched for today; {date} was not captured")
    run_fetch(fetch, date)
    landed = table_has_partition(profile, table, date)           # re-check: "success" may land nothing
    return Availability(landed, True, "" if landed else f"fetch ran but no {table} landed for {date}")
    # never substitute another date
```

## §6 Scaffold with anchors

```python
#!/usr/bin/env python3
"""scaffold_tenant.py <id> [--apply | --check]   (default: print the plan, write nothing)"""
import re, sys
from pathlib import Path

ANCHORED_EDITS = {
    "deploy/deploy_tenant.sh": ("# TENANT-SCAFFOLD: WRAPPER-CASE", '  {id}) SCOPE={id} ;;\n'),
    "deploy/render_env.py":    ("# TENANT-SCAFFOLD: SECRET-KEYS", '    "{id}": ["{ID}_API_TOKEN"],\n'),
    "deploy/setup_host.sh":    ("# TENANT-SCAFFOLD: DATA-ROOT", '  {id}) DATA_ROOT=/srv/app-data/{id} ;;\n'),
}


def insert_once(text: str, anchor: str, snippet: str) -> str:
    if snippet in text:
        return text                                   # idempotent: a re-run changes nothing
    count = text.count(anchor)
    if count != 1:
        raise SystemExit(f"anchor {anchor!r} found {count} times (need exactly 1): refusing")
    return text.replace(anchor, snippet + anchor)     # insert above the anchor, keep the anchor


def plan(tid: str) -> list[tuple[Path, str]]:
    files = [(Path(f"tenants/{tid}/manifest.json"), MANIFEST_TEMPLATE.format(id=tid)),
             (Path(f"tenants/{tid}/adapter.py"), 'raise SystemExit("adapter for %s not written yet")\n' % tid),
             (Path(f"deploy/{tid}.sh"), WRAPPER_TEMPLATE.format(id=tid))]
    for path, (anchor, snippet) in ANCHORED_EDITS.items():
        p = Path(path)
        files.append((p, insert_once(p.read_text(), anchor, snippet.format(id=tid, ID=tid.upper()))))
    return files


def check(tid: str) -> int:
    problems = [f"{p}: missing wiring for {tid}" for p in ANCHORED_EDITS
                if tid not in Path(p).read_text()]
    # go further than string checks: load the manifest through the real loader, and run the
    # validator on a tiny fixture tree for this tenant
    try:
        load_profile(tid)
    except Exception as exc:
        problems.append(f"manifest does not load: {exc}")
    for p in problems:
        print("MISSING", p)
    return 1 if problems else 0
```

## §7 Onboarding definitions of done

**Data/capability onboarded**
- [ ] Validator: zero ERRORs on the tenant's canonical tree.
- [ ] Every shared capability the tenant enables produces output on real data.
- [ ] Coverage gaps measured and handed to the tenant's domain expert; no fabricated fallbacks.
- [ ] Acceptance tests registered for each enabled capability.

**Production onboarded**
- [ ] `scaffold_tenant.py <id> --check` passes; full gate green.
- [ ] Host, service identity, bucket, chat app, secret source are tenant-isolated.
- [ ] Restore done once; routine data flow is host → backup only.
- [ ] Health, canonical validation, backup timer and capture timers observed on the live host.
- [ ] Parallel run against real requests before replacing an existing system.
