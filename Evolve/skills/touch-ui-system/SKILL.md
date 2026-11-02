---
name: touch-ui-system
description: Build a frontend whose consistency is structural rather than remembered, for touch devices in real working conditions (tablets on a shop floor, kiosks, second-language users). Covers closed design-token scales (px type with the floor as a token, 4-pt spacing, radii, control heights with reasons, one motion curve), text and tap-target floors on base element selectors with reasoned opt-outs, static gates that fail literal sizes, bypasses and dead exceptions, a component registry enforced both ways (one control per concept), backlog-as-code with done-probes, one scoped feedback path, transport-driven busy state, press-once controls, conflict replay that keeps edits, one auth-aware fetch, flash-free theming, node-executable UI logic with parity tests, and a migration order (values, consolidate, sweep). Use when building or refactoring a tablet, phone or kiosk frontend, introducing a design system, consolidating duplicate components, or adding UI checks to CI.
---

# Touch UI system: compliance by construction

> Copying the nearest CSS block and nudging it is how a console reaches dozens of font sizes,
> many border radii, three pickers for one concept and two date formats. Consistency must be
> something the code *is*, not something people remember.

**The meta-rule.** For every UX rule, ask: *what makes a NEW thing compliant without anyone
remembering?* Put the rule there (a base selector, the transport, a component constructor, a
derivation). Then gate it so that (1) a bypass fails, (2) every exception is a keyed entry with
a written reason, (3) an exception whose target no longer exists fails, (4) the gate saw a
plausible amount of input (a sanity floor).


**On React · TypeScript · Vite · Tailwind:** close the scales in `@theme` (v4) or by replacing `theme` keys (v3); floors in `@layer base` with `:where()`; a lint rule against arbitrary values; a registry and backlog in TS with vitest gates; TanStack Query for busy state and dedupe; Playwright at 360/768/1280 px. Templates §11–§12.

## 1. Closed token scales

- **Type in px**, a short named scale where each step lists who uses it; the smallest step
  **is the floor** (e.g. `--fs-floor: 14px`) and nothing renders below it. (A rem scale on a
  non-16px body is "a scale of a scale" and the floor stops being a floor.)
- Display figures (big KPI numbers) get their own token beside the scale, not a text step.
- **Space**: a 4-pt scale `--space-1…--space-7`; one step doubles as the minimum gap between targets.
- **Radii**: three (`--radius-field`, `--radius-card`, `--radius-pill`).
- **Control heights**: `--tap-min: 48px`, `--tap-primary: 56px`, `--tap-row: 64px` — each
  with a stated reason, "and no fourth".
- **Motion**: one curve, three durations; transition named properties only (never `all`);
  a pressed state (`:active { transform: scale(.97) }`).
- Size tokens are **not** redeclared for dark mode ("a millimetre is not a colour").
- Land tokens **before** the sweep that consumes them (adding them changes no pixel); sweep
  by **role**, not by nearest pixel; dry-run until every declaration is accounted for.

## 2. Floors on base element selectors

```css
button, select, textarea, summary, [role="button"],
input:where(:not([type="range"], [type="checkbox"], [type="radio"])) {
  min-height: var(--tap-min);
}
```
- An opt-in list of selectors left almost every control under 48px, and a panel written the
  day after the spec landed under the floor again. The base selector makes every new control
  comply by default.
- **Keep the floor at element-level specificity** so a one-class component can opt *up*
  (`.big { min-height: var(--tap-primary) }`): wrap the input exclusions in `:where()`, which adds
  zero specificity. A bare `input:not(…)` scores (0,1,1) and beats a single class on inputs;
  chained `:not()`s scored even higher in the reference system and
  silently beat every opt-up for a day. Document the engine floor (older engines drop the
  whole rule when they can't parse a `:where()`/`:not()` selector list).
- **A floor is not a ceiling**: an explicit `min-width` replaces a flex item's automatic
  minimum and clips its label — pair it with `flex-shrink: 0`.
- Opt-outs only for **non-targets** (a glyph inside a button, a legend chip), on that selector,
  with a reason, in a keyed exception table the gate reads.
- Retire smaller "tap" tokens (a 44px value is a phone convention, not a floor).

## 3. Static gates (CI fails, not reviewers)

Gate in tests over the source (see `test-gates` §9 and its templates §7 for the parsing techniques):
every `font-size` reads `var(--fs-*)` · the scale is strictly increasing and the floor exact ·
no `height`/`min-height` below the floor outside exceptions · no dead exception · every opt-up
token beats every floor that could match the same element (a small specificity calculator,
self-tested) · CSS syntax (a missing semicolon "welds" two declarations) · both dark palettes
identical and no colour literal outside the palette · theme script loads before the stylesheet ·
no top-level function declared twice · bare-wired handlers never receive the Event as a domain
object · payload counts equal list lengths (no silent truncation) · uppercase only where
allowlisted with a reason. **Strip comments first** — a gate once passed on its own explanatory comment.

## 4. A component registry the build enforces

A code-resident catalogue (`ui/registry.py|ts`): `id, name, answers, status (live | scattered
| proposed), dialogs, entries, endpoints, primitives, used_by, rules, consolidate_to`.
- **`answers`**: the one question a user is asking. "If it needs 'and', you have two widgets."
- **`rules`**: domain rules that would be lost in a rewrite, each with its incident.
- **Primitive** (no domain knowledge: Picker, Field, Toolbar) vs **widget** (owns endpoints and rules).
- Gate both ways: every `<dialog>` in the markup is claimed; every claimed dialog, entry point
  and endpoint exists; a `scattered` widget names an existing `consolidate_to`; notes cite
  symbols, never `file:line`.
- **Search the registry before building anything interactive**; extend a widget rather than add
  the Nth implementation. A consolidation can "close by correction" — one action in two
  contexts is not a duplicate.

## 5. Backlog as code

`ui/backlog.py` items: `id, phase, order, size, title, why, probe` where a probe is
`("present" | "absent", file, needle)` or `None` for a decision. The test **fails an item whose
probe now reads DONE** (message: tighten the probe or delete the item), fails a probe whose file
is missing, and renders derived items from the registry (`scattered` → consolidate, `proposed` →
build). "What to work on next lives in code, not prose" — a prose backlog is wrong within weeks.

## 6. One control per concept

- **Picker** primitive: fixed anatomy (header, context, current answer, search, list, footer);
  `create()` throws on missing parts; `open()` is the single entry and resets search/footer/
  current every time; an add-panel **replaces** the list so its submit is always reachable;
  meaning comes from caller callbacks (`onSearch`, `onAdd`, `emptyText`), not modes.
- **Picker-backed field**: a trigger button + a hidden input that keeps the original id —
  readers keep reading `.value`, so migration is a markup swap; writes go through one setter.
- Several catalogues in one modal via **dispatch tables** (sources, footers, empty texts) that a test
  holds to one key set — a seventh screen joins by adding a row.
- **DateField**: one control, UTC date math, exactly a few formatters built from fixed
  weekday/month tables — never the device locale ("one control is not one format").
- **OverflowList**: one threshold, in one module, a real button chip.
- Never a native `<select>` for lists that can exceed ~15 items. **Sweep by mechanism, not by
  place** (a hand-count of duplicate list controls was wrong twice).

## 7. Feedback, busy, single flight

- **One feedback path**: `notify(scope, …)` where scope maps to the views it belongs to; drop
  outcomes whose workspace is no longer on screen; successes fade, **failures stay until
  dismissed**; render inside an open modal's top layer (watch the dialog's `open` attribute —
  a `close` event was measured not firing).
- **Busy comes from the transport**: count in-flight requests inside the one fetch wrapper, so
  every screen is covered by construction; grace delay (~200 ms) + minimum visible (~400 ms);
  determinate progress never moves backwards.
- **Press-once**: `pressOnce(control, label, run)` disables during the call, restores the label
  only if it still shows the busy word, and leaves "enabled" to the screen's state function.
- Client single flight: reuse the pending promise per key (with a generation counter so a
  `forget()` discards in-flight results); guard re-entrance with state flags, not button state;
  a request sequence number for last-response-wins.

## 8. Refusals, conflicts, sessions

- **Conflict replay** (see `safe-writes` §7): never lose typed work; show "Pending" badges and a
  count on Approve; never auto-save a merge.
- **One auth-aware fetch**: an expired proxy session answers 401; recovery is **one shared
  promise** that every concurrent caller awaits (a second 401 must not race ahead), the **actor is pinned**
  (refuse to replay under another identity), one retry per cause, POST options built by a
  factory so the CSRF header is rebuilt on retry; a 403 `session-token-expired` refreshes the
  edit token and retries once (only if the token actually changed); network errors and other
  403s never start recovery. Test it as a pure state machine under node.

## 9. Theme and format without flashes

Small synchronous scripts **before** the stylesheet (external files, for a `script-src 'self'`
CSP) set theme and format; everything else `defer`. Theme is three-state — "system" is **not
stored**, only explicit choices are. The dark palette is written twice (`@media
(prefers-color-scheme: dark) :root:not([data-theme=light])` and `:root[data-theme=dark]`) —
duplication the CSS language forces is fine **if a test compares the copies**. Format (phone /
tablet / desktop) defaults to the device (`any-pointer: coarse`); layouts use container
queries. **Derive, don't author**: card labels from `<thead>`, menus from their model.

## 10. Field rules that each broke once

No native `required`/constraint bubbles (they speak the browser's language, not the app's) ·
measurement inputs `step="any"` · a base `[hidden] { display: none !important }` rule ·
split rendering into a **structure** path (on pick) and a **keystroke** path that never rebuilds
a focused control's ancestor · never show hashes, run ids or file paths · a write action is
never styled as a filter pill · disabled controls carry their reason beside them · no hover-only
signals · tables become cards on phones.

**Words** (people read the screen in a second language, under time pressure):
- Name the **action the person is doing** ("Put Ravi on station 4"), not the record the system
  writes ("Create assignment override").
- **One name per concept, app-wide** — keep a glossary and use it in labels, toasts and errors.
- Keep the codes and names users already know (from their source systems) rather than renaming them.
- No page-level explanatory prose unless it is derived from what the code does; prose that
  describes behaviour goes stale (inaccurate purpose lines were withdrawn rather than rewritten).

## 11. Test UI logic without a browser — and with one

- Modules as IIFEs exporting one namespace to `window`/`globalThis`; pure halves exported;
  clocks, timers and fetch injected → run under node from the test suite; **parity tests**
  against the server's implementation on discriminating fixtures.
- Geometry and focus need a real engine: a headless browser asserting overlays sit inside the
  viewport and focus survives typing; a device-check page for native touch behaviour; a mock
  server serving the **real** static files on the LAN for tablet checks.
- Measure on the live DOM, A/B by reverting only the stylesheet; "right-sized is not reachable".

## 12. Migration order

**Phase 0** reachability bugs → **Phase 1 values** (tokens, base floors, type sweep) →
**Phase 2 consolidate** (one picker, one date field, one overflow list…) → **Phase 3 structural
sweep** (toolbar, field, feedback, page header, rows, action bar). Values first so each widget
is built once in the new vocabulary; consolidation before the sweep, or you restyle seven
pickers and then delete five. Each step ships alone and is measured; re-count by mechanism
before declaring a sweep done.

## Translation: React · TypeScript · Vite · Tailwind · TanStack Query · Playwright

| Concept | Your stack |
|---|---|
| Closed scales | `tailwind.config.ts` `theme` (replace, don't `extend`, fontSize/spacing/borderRadius) so only tokens exist |
| Forbid literals | ESLint rule banning arbitrary values (`text-[13px]`, `h-[40px]`, raw hex) + a vitest scan of `src/**/*.tsx` as backstop |
| Base floors | `@layer base { button, [role=button], select, textarea, input:where(:not([type=checkbox],[type=radio],[type=range])) { min-height: 48px } }` — in Tailwind v4 `@layer` is a native cascade layer (utilities win); in v3 it is not, so the `:where()` matters even more |
| Closed scales (v4) | `@theme { --text-*: initial; --text-floor: 14px; … }` clears the defaults so only your steps exist |
| Registry | `src/ui/registry.ts` + a vitest that fails on any `<Dialog`/`<Sheet` not claimed and on claimed entries that no longer exist |
| Backlog-as-code | `src/ui/backlog.ts` with probes + a vitest that fails DONE items |
| Busy from transport | `useIsFetching()`/`useIsMutating()` driving one top bar; mutations disable their trigger |
| Single flight | TanStack Query dedupes by query key; mutations keyed per subject |
| Conflict replay | `onError` 409 → refetch → re-apply local edits to untouched rows → mark dirty |
| Auth fetch | one `apiFetch()` wrapper with the attempt/actor-pinned recovery |
| Geometry/focus | Playwright at 360/768/1280 widths: no horizontal scroll, overlays in viewport, focus kept |

Templates: [references/templates.md](references/templates.md).

## Related skills
`test-gates` · `safe-writes` · `console-backend` · `agentic-workbench`
