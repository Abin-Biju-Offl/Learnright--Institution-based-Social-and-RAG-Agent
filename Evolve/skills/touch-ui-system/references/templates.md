# touch-ui-system — templates

## §1 Token block

```css
:root {
  /* TYPE — px on purpose: body is not 16px, so a rem scale would be a scale of a scale.
     Closed: a new step costs an edit here AND in tests/test_ui_type_scale.py. */
  --fs-floor: 14px;      /* THE FLOOR: captions, timestamps, chip text */
  --fs-label: 15px;     /* field labels, table headers */
  --fs-body: 16px;      /* running text, table cells */
  --fs-heading: 17px;      /* card and section heads */
  --fs-title: 20px;     /* page titles */
  --fs-display: 26px;   /* the one number a screen is about */
  --fs-figure: 48px;      /* a figure, not text: KPI tiles only */

  /* SPACE — 4-point; --space-2 is also the minimum gap between two targets */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;

  /* RADII */
  --radius-field: 10px; --radius-card: 14px; --radius-pill: 999px;

  /* CONTROL HEIGHTS — each with a reason, and no fourth */
  --tap-min: 48px;      /* the touch floor (gloved finger, moving hand) */
  --tap-primary: 56px;   /* primary actions at the end of a flow */
  --tap-row: 64px;  /* tappable list rows carrying two lines */

  /* MOTION */
  --ease: cubic-bezier(.2, .8, .2, 1);
  --dur-1: 120ms; --dur-2: 200ms; --dur-3: 320ms;

  /* COLOUR — light; dark lives in two blocks below (and a test keeps them equal) */
  --bg: #f7f7f5; --surface: #ffffff; --ink: #1c1c1a; --ink-2: #55554f; --accent: #2457d6;
  --shadow-rgb: 20 20 18;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg: #121211; --surface: #1b1b19; --ink: #f2f2ee; --ink-2: #b4b4ac; --accent: #7aa2ff; --shadow-rgb: 0 0 0; }
}
:root[data-theme="dark"] { --bg: #121211; --surface: #1b1b19; --ink: #f2f2ee; --ink-2: #b4b4ac; --accent: #7aa2ff; --shadow-rgb: 0 0 0; }
```

## §2 Base floor, motion, hidden

```css
/* :where() contributes ZERO specificity, so every selector here stays at element level (0,0,1)
   or a lone attribute (0,1,0) — and a one-class opt-up such as `.big { min-height: var(--tap-primary) }`
   placed later wins on buttons AND inputs. A bare `input:not(...)` would score (0,1,1) and beat it;
   chained :not()s score higher still. */
button, select, textarea, summary, [role="button"],
input:where(:not([type="range"], [type="checkbox"], [type="radio"])) {
  min-height: var(--tap-min);
}
button, [role="button"], a, summary {
  transition: background-color var(--dur-1) var(--ease), color var(--dur-1) var(--ease),
              box-shadow var(--dur-2) var(--ease), transform var(--dur-1) var(--ease);
}
button:active, [role="button"]:active { transform: scale(0.97); }
[hidden] { display: none !important; }      /* no author `display` rule can beat it */
.icon-action { min-width: var(--tap-min); flex-shrink: 0; }   /* a floor, not a ceiling */
```

## §3 Gates (Python, stdlib)

```python
# tests/test_ui_type_scale.py
import re
from pathlib import Path

CSS = re.sub(r"/\*.*?\*/", "", Path("static/styles.css").read_text(encoding="utf-8"), flags=re.S)
SCALE = (("--fs-floor", 14), ("--fs-label", 15), ("--fs-body", 16), ("--fs-heading", 17),
         ("--fs-title", 20), ("--fs-display", 26))
UPPERCASE_EXCEPTIONS = {".chip-status": "status chips are codes, not words"}

FIGURE_TOKENS = {"--fs-figure"}            # display figures live beside the text scale, by name
MIN_DECLARATIONS = 1                        # raise as the stylesheet grows (a sanity floor, not a target)

declared = {name: int(px) for name, px in re.findall(r"(--fs-[\w-]+)\s*:\s*(\d+)px", CSS)}
for name, px in SCALE:
    check(declared.get(name) == px, f"{name} is declared at {px}px in the stylesheet")
extra = set(declared) - {n for n, _ in SCALE} - FIGURE_TOKENS
check(not extra, f"the scale is CLOSED: undeclared steps {sorted(extra)}")
values = [declared[n] for n, _ in SCALE if n in declared]
check(values == sorted(set(values)), "the DECLARED scale is strictly increasing")
check(min(values, default=0) >= 14, "nothing in the scale is below the 14px floor")

sizes = re.findall(r"font-size\s*:\s*([^;}]+)", CSS)
shorthands = re.findall(r"(?<![-\w])font\s*:\s*([^;}]+)", CSS)
check(len(sizes) + len(shorthands) >= MIN_DECLARATIONS, f"sanity: saw {len(sizes)} font-size declarations")
allowed = {f"var({n})" for n, _ in SCALE} | {f"var({n})" for n in FIGURE_TOKENS}
bad = [v.strip() for v in sizes if v.strip() not in allowed]
bad += [v.strip() for v in shorthands if not any(a in v for a in allowed)]
check(not bad, f"every font size reads a SCALE token (font: shorthand included): {sorted(set(bad))[:10]}")

rules = re.findall(r"([^{}]+)\{([^{}]*)\}", CSS)
upper = {sel.strip() for sel, body in rules if re.search(r"text-transform\s*:\s*uppercase", body)}
for sel in upper:
    check(any(k in sel for k in UPPERCASE_EXCEPTIONS), f"uppercase without a reason: {sel}")
for key in UPPERCASE_EXCEPTIONS:
    check(any(key in sel for sel in upper), f"dead exception {key!r}: no live rule uses it")
```

```python
# tests/test_ui_touch_floor.py  (core checks)
FLOOR_EXCEPTIONS = {
    ".legend-chip": "not a target: a colour key inside a legend",
    ".icon-in-button svg": "a glyph inside a 48px button",
}
floor_rules = [sel for sel, body in rules
               if "min-height" in body and "var(--tap-min)" in body and "button" in sel]
check(len(floor_rules) == 1, "exactly one base floor rule")
base = floor_rules[0]
for part in ("button", "select", "textarea", "summary", '[role="button"]', "input:where(:not("):
    check(part in base, f"the base floor reaches {part}")
check(not re.search(r"\.[A-Za-z]", base), "the base floor names no class (it must stay element-level)")
for sel, body in rules:
    for prop, val in re.findall(r"(min-height|height)\s*:\s*(\d+)px", body):
        if int(val) < 48 and not any(k in sel for k in FLOOR_EXCEPTIONS):
            check(False, f"{sel.strip()}: {prop} {val}px is under the floor")
for key in FLOOR_EXCEPTIONS:
    check(any(key in sel for sel, _ in rules), f"dead exception {key!r}")
```

## §4 Registry entry + bidirectional gate

```python
# app/ui/registry.py
WIDGETS = [
    {
        "id": "person-picker",
        "name": "Person picker",
        "answers": "Who should do this?",                 # one question; "and" means two widgets
        "status": "live",                                 # live | scattered | proposed
        "dialogs": ("person-dialog",),
        "entries": ("openPersonPicker",),                 # top-level functions in app.js
        "endpoints": ("/api/people/candidates",),
        "primitives": ("Picker",),
        "used_by": ("plan", "daily"),
        "rules": (
            "Busy elsewhere is a LABEL, never a hidden row (a filter once hid most candidates).",
            "Rank by rating, then same unit, then name — never by id.",
        ),
        "consolidate_to": None,                           # required when status == 'scattered'
    },
]
```

```python
# tests/test_ui_registry.py
html = Path("static/index.html").read_text(encoding="utf-8")
js = strip_js_comments(Path("static/app.js").read_text(encoding="utf-8"))
dialogs = set(re.findall(r"<dialog[^>]*\bid\s*=\s*['\"]([^'\"]+)['\"]", html))
claimed = [d for w in WIDGETS for d in w["dialogs"]]
for d in sorted(dialogs - set(claimed)):
    check(False, f"<dialog id={d}> is claimed by no widget — catalogue it before shipping")
for d in claimed:
    check(d in dialogs, f"claimed dialog {d} exists"); check(claimed.count(d) == 1, f"{d} claimed once")
for w in WIDGETS:
    for fn in w["entries"]:
        check(re.search(rf"^(?:async\s+)?function\s+{fn}\s*\(", js, re.M), f"{w['id']}: entry {fn}() exists")
    for ep in w["endpoints"]:
        check(f'"{ep}' in js or f"'{ep}" in js or f"`{ep}" in js, f"{w['id']}: endpoint {ep} is called")
    if w["status"] == "scattered":
        check(any(x["id"] == w.get("consolidate_to") for x in WIDGETS), f"{w['id']}: consolidation target exists")
    for text in w["rules"]:
        check(not re.search(r"\w+\.(py|js|css|html):\d+", text), f"{w['id']}: cite symbols, not line numbers")
```

## §5 Backlog as code

```python
# app/ui/backlog.py
ITEMS = [
    {"id": "one-date-control", "phase": 2, "order": 1, "size": "M",
     "title": "Replace the two date controls with DateField",
     "why": "two formats on one screen; device-locale rendering differs per tablet",
     "probe": ("present", "static/index.html", 'type="date"')},      # OPEN while the needle exists
    {"id": "floor-on-base", "phase": 1, "order": 2, "size": "S",
     "title": "Touch floor on the base element selector",
     "why": "opt-in lists rot: new controls start non-compliant",
     "probe": ("absent", "static/styles.css", "min-height: var(--tap-min)")},
    {"id": "decide-bulk-edit", "phase": 3, "order": 1, "size": "—",
     "title": "Decide whether bulk edit is in scope", "why": "pilot evidence pending", "probe": None},
]


def state(item) -> str:
    if item["probe"] is None:
        return "DECISION"
    kind, file, needle = item["probe"]
    p = Path(file)
    if not p.exists():
        return "MISSING"
    found = needle in p.read_text(encoding="utf-8")
    return "OPEN" if (found if kind == "present" else not found) else "DONE"
```
```python
# tests/test_ui_backlog.py
for item in ITEMS:
    s = state(item)
    check(s != "DONE", f"{item['id']} is DONE — TIGHTEN its probe if a rename fooled it, else DELETE it")
    check(s != "MISSING", f"{item['id']}: probe file missing (never read as done)")
```

## §6 Module shell, busy tracker, press-once

```js
// static/busy.js — loads in the browser AND under node (tests)
(function (root) {
  "use strict";
  function tracker({ graceMs = 200, minVisibleMs = 400, now = () => Date.now(),
                     setTimer = setTimeout, clearTimer = clearTimeout, ui }) {
    let inFlight = 0, shownAt = null, pending = null;
    return {
      start() {
        inFlight += 1;
        if (inFlight === 1 && shownAt === null && !pending) {
          pending = setTimer(() => { pending = null; shownAt = now(); ui.show(); }, graceMs);
        }
      },
      end() {
        inFlight = Math.max(0, inFlight - 1);
        if (inFlight > 0) return;
        if (pending) { clearTimer(pending); pending = null; return; }     // fast: never shown
        const left = Math.max(0, minVisibleMs - (now() - shownAt));
        setTimer(() => { if (inFlight === 0) { shownAt = null; ui.hide(); } }, left);
      },
    };
  }
  async function pressOnce(control, label, run) {
    const original = control.textContent;
    control.disabled = true;                 // press-once for the whole call
    control.textContent = label;
    try { return await run(); }
    finally {
      if (control.textContent === label) control.textContent = original;
      // "enabled" belongs to the screen's state function, not to this helper:
      control.dispatchEvent(new CustomEvent("busy-done", { bubbles: true }));
    }
  }
  root.Busy = Object.freeze({ tracker, pressOnce });
})(typeof window === "undefined" ? globalThis : window);
```
Wire `tracker.start()/end()` inside the ONE `api()`/`apiPost()` wrapper — never per screen.

## §7 Scoped notifications

```js
const TOAST_SCOPES = { plan: ["plan", "plan-day"], daily: ["daily"], quality: ["quality"] };
function notify(scope, kind, text) {
  if (!TOAST_SCOPES[scope]?.includes(state.view)) return null;   // the user left: drop it
  const host = document.querySelector("dialog[open]") || document.body;  // top layer when modal
  const el = renderToast(kind, text);
  host.append(el);
  if (kind === "success") setTimeout(() => el.remove(), 7000);         // failures stay
  trimToasts(host, 4);
  return el;
}
```

## §8 Conflict replay

```js
// static/conflict.js
function diffEdits(baseline, current, { key, compare }) {
  const base = new Map(baseline.map(r => [r[key], r]));
  return current.filter(r => compare.some(f => (base.get(r[key]) || {})[f] !== r[f]))
                .map(r => ({ key: r[key], from: base.get(r[key]) || null, to: r }));
}
function replayEdits(fresh, edits, { key, compare }) {
  const rows = new Map(fresh.map(r => [r[key], { ...r }]));
  const result = { applied: [], conflicted: [], vanished: [] };
  for (const e of edits) {
    const now = rows.get(e.key);
    if (!now && e.from) { result.vanished.push(e.key); continue; }    // they removed it
    const sameAsMine = now && compare.every(f => now[f] === e.to[f]);
    if (sameAsMine) { result.applied.push(e.key); continue; }         // a colleague agreed: no conflict
    const theirsChanged = now && e.from && compare.some(f => now[f] !== e.from[f]);
    if (theirsChanged) { result.conflicted.push(e.key); continue; }   // theirs stands; we report
    rows.set(e.key, { ...(now ?? e.to), ...pick(e.to, compare) });   // a row I ADDED keeps its key
    result.applied.push(e.key);
  }
  return { rows: [...rows.values()], ...result };    // the screen is marked dirty; never auto-saved
}
```

## §9 One auth-aware fetch

```js
function createSession({ fetchImpl, reauth, currentActor, refreshCsrf }) {
  let attempt = null;                       // ONE recovery promise shared by concurrent 401s
  async function recover(actorBefore) {
    if (!attempt) {
      attempt = reauth().finally(() => { attempt = null; });
    }
    await attempt;                          // every concurrent caller WAITS for the same re-auth
    if ((await currentActor()) !== actorBefore) throw new Error("actor-changed"); // never replay as someone else
  }
  async function request(url, makeOptions) {           // options from a FACTORY: headers rebuilt per try
    const actorBefore = await currentActor();
    let res = await fetchImpl(url, makeOptions());
    if (res.status === 401) {                           // the proxy's login expired
      await recover(actorBefore);
      res = await fetchImpl(url, makeOptions());        // exactly one retry per cause
    }
    if (res.status === 403) {                           // the app's edit token expired (server restarted)
      const body = await res.clone().json().catch(() => ({}));
      if (body.code === "session-token-expired") {
        const sent = makeOptions().headers?.["X-CSRF-Token"];
        const fresh = await refreshCsrf();
        if (fresh && fresh !== sent) res = await fetchImpl(url, makeOptions());   // once, only if it changed
      }
    }
    return res;                                         // other 403s and network errors: no recovery
  }
  return { request };
}
```

## §10 Theme before first paint

```js
// static/theme.js — loaded synchronously BEFORE styles.css (an external file: CSP script-src 'self')
(function () {
  try {
    const t = localStorage.getItem("theme");          // only explicit choices are stored
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
  } catch (_) { /* private mode: system theme applies */ }
})();
```
Gate: parse both dark blocks into `{token: value}` dicts and require equality; require
`theme.js` appear before `styles.css` in `index.html`.

## §11 Tailwind / ESLint translation

```ts
/* Tailwind v4 (CSS-first): close the scales by clearing the defaults, then declaring yours */
@import "tailwindcss";
@theme {
  --text-*: initial;
  --text-floor: 14px; --text-label: 15px; --text-body: 16px; --text-heading: 17px;
  --text-title: 20px; --text-display: 26px;
  --radius-*: initial;
  --radius-field: 10px; --radius-card: 14px; --radius-pill: 999px;
}
@layer base {
  /* native cascade layers in v4: utilities (a later layer) win over this floor */
  button, select, textarea, summary, [role="button"],
  input:where(:not([type="range"], [type="checkbox"], [type="radio"])) { min-height: 48px; }
}
```
```ts
// Tailwind v3 equivalent: REPLACE scales (no extend) so only tokens exist
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    fontSize: { meta: "14px", label: "15px", body: "16px", head: "17px", title: "20px", display: "26px" },
    spacing: { 0: "0", 1: "4px", 2: "8px", 3: "12px", 4: "16px", 6: "24px", 8: "32px", 12: "48px", 14: "56px", 16: "64px" },
    borderRadius: { control: "10px", card: "14px", pill: "999px" },
    extend: { colors: { bg: "var(--bg)", surface: "var(--surface)", ink: "var(--ink)", accent: "var(--accent)" } },
  },
};
```
```js
// Prefer an existing plugin rule for arbitrary values (e.g. a Tailwind lint plugin's
// "no arbitrary value" rule). As a fallback, catch ANY utility with a bracket value — in string
// literals and template literals alike (text-[13px], px-[7px], max-h-[40vh], bg-[#fff]):
{ rules: { "no-restricted-syntax": ["error",
  { selector: "Literal[value=/(^|\\s)[a-z][\\w-]*-\\[[^\\]]+\\]/]",
    message: "Use a token class; arbitrary values bypass the closed scale." },
  { selector: "TemplateElement[value.raw=/(^|\\s)[a-z][\\w-]*-\\[[^\\]]+\\]/]",
    message: "Use a token class; arbitrary values bypass the closed scale." }] } }
```

## §12 Playwright truths a static gate cannot see

```ts
for (const width of [360, 768, 1280]) {
  test(`no horizontal scroll and dialogs in viewport @${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("button", { name: "Pick a date" }).click();
    const box = await page.locator("dialog[open]").boundingBox();
    expect(box!.y + box!.height).toBeLessThanOrEqual(800);       // right-sized is not reachable
  });
}
test("typing keeps focus", async ({ page }) => {
  await page.goto("/edit");
  const input = page.getByLabel("Operation");
  await input.type("WELD-2");
  await expect(input).toBeFocused();                              // value kept ≠ focus kept
});
```
