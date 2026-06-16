# Handoff: CareLens AI — Medical Desert Planner

## Overview
The Medical Desert Planner is an analyst-facing dashboard for identifying "medical deserts" — geographic regions where care-gap **risk** is high. Its core idea: a region is only a **confirmed desert** when high risk is backed by high **data confidence**. High risk on thin evidence is a **blind spot** to investigate, not a conclusion. The analyst filters by clinical capability (ICU, Maternity, etc.) and geographic grain (State / District / PIN), reads the map / quadrant / ranked views, drills into a region's evidence ledger, can override the model verdict, leave notes, watchlist regions, save scenarios, and export an action plan.

## About the Design Files
The files in this bundle are **design references created in HTML** — a working prototype showing the intended look, layout, and behavior. They are **not production code to copy directly.** The task is to **recreate this design in your target codebase** (React, Vue, Svelte, etc.) using its existing component library, state-management, and data-fetching patterns. If no codebase exists yet, pick an appropriate framework (React + a charting/`d3` setup works well here) and implement there.

Note: the prototype uses a small custom runtime (`support.js`, the `<x-dc>` / `<sc-for>` / `<sc-if>` tags). **Do not port that runtime.** Read it only to understand structure and behavior; rebuild with idiomatic components in your stack.

## Fidelity
**High-fidelity (hifi).** Final colors, typography, spacing, layout, and interactions are all specified below and present in the file. Recreate the UI faithfully using your codebase's libraries. The data is **synthetically generated** in the prototype (deterministic hash-based fake metrics) — in production, replace it with your real data source; the visual + interaction spec stands.

---

## Layout

Full-viewport app, **min-width 1340px** (desktop-only), `100vh` tall, no page scroll — internal panels scroll.

```
┌──────────────────────────────────────────────────────────────┐
│  TOP BAR  (66px)  logo · search · theme toggle · scenario · export │
├──────────┬─────────────────────────────────┬───────────────────┤
│ LEFT     │  CENTER                          │  RIGHT            │
│ RAIL     │  summary band (4 stat cards)     │  ranked list      │
│ 262px    │  view card (Map | Quadrant tabs) │  OR region detail │
│          │  1fr                             │  396px            │
└──────────┴─────────────────────────────────┴───────────────────┘
```

Body is `display:grid; grid-template-columns: 262px 1fr 396px;`.

---

## Design Tokens

Themed via CSS custom properties on `:root`, with a `[data-theme="dark"]` override block. Body transitions `background`/`color` over `.25s`.

### Light theme
| Token | Value | Use |
|---|---|---|
| `--bg` | `#eef0f3` | app background |
| `--panel` | `#ffffff` | cards, bars, rails |
| `--panel-2` | `#f4f5f8` | inset controls (search, segmented) |
| `--panel-3` | `#f8f9fb` | nested cards, textarea |
| `--border` | `#e2e4ea` | panel borders |
| `--border-2` | `#e6e8ee` | control borders |
| `--border-3` | `#e9ebf0` | hairline dividers |
| `--ink` | `#1b1d26` | primary text |
| `--ink-2` | `#2d313d` | secondary headings |
| `--muted` | `#565c6b` | body text |
| `--faint` | `#5f6675` | labels, captions |
| `--accent` | `#4f46e5` (indigo) | active states, watchlist star, focus chip |
| `--accent-soft` | `#eef0ff` | accent backgrounds |
| `--accent-border` | `#e0e2fb` | accent borders |
| `--accent-ink` | `#312e81` | text on accent |
| `--solid` | `#1b1d26` | primary button bg |
| `--solid-ink` | `#ffffff` | primary button text |
| `--callout-bg` / `--callout-border` / `--callout-ink` / `--callout-strong` | `#fbf7f2` / `#f0e6d8` / `#8a7a5e` / `#7a6320` | the "confirmed desert" explainer callout |
| `--warn-bg` / `--warn-border` / `--warn-ink` | `#fdf3e6` / `#f3e2cb` / `#b06a1f` | override-active banner |

### Dark theme (`[data-theme="dark"]`)
`--bg:#0c0e14` · `--panel:#1d222e` · `--panel-2:#151a23` · `--panel-3:#191e28` · `--border:#2b3140` · `--ink:#eef1f6` · `--ink-2:#ccd2dd` · `--muted:#9aa1b3` · `--faint:#8a92a6` · `--accent:#8a90ff` · `--accent-soft:#222a4d` · `--accent-border:#36417c` · `--solid:#e9ecf2` · `--solid-ink:#171a22`. (Quadrant tints, legend bg, callout, warn all have dark variants — see the `:root[data-theme="dark"]` block in the HTML for exact values.)

### Verdict colors (fixed, not themed)
| Verdict | Dot/accent | Ink | Badge bg | Meaning |
|---|---|---|---|---|
| **Confirmed desert** | `#d23f2d` | `#a32b1c` | `#fbeae7` | high risk + high confidence |
| **Blind spot** | `#e0a32b` | `#a9781a` | `#fcf3e3` | high risk + low confidence — investigate |
| **Adequately served** | `#2f9e6b` | `#1f7a50` | `#e8f5ee` | low risk + high confidence |
| **Unverified** | `#9aa0ad` | (muted) | `#f1f2f5` | low risk + low confidence |

Verdict threshold: risk **and** confidence each compared against **58** (0–100 scale).

### Evidence-strength colors
Strong `#2f9e6b` · Partial `#e0a32b`/`#c08416` · Weak `#d6d9e0`/faint.

### Risk gradient (continuous, used for map fill, risk numbers, risk bars)
Interpolated in **OKLCH** across these stops (risk 0→100):
`0 → oklch(0.76 0.10 150)` (green) · `40 → oklch(0.85 0.13 95)` (yellow) · `66 → oklch(0.70 0.16 52)` (orange) · `100 → oklch(0.55 0.19 27)` (red). The map legend strip renders this as `linear-gradient(90deg,#79c39a,#e8d36a,#e79a3d,#d23f2d)`.

### Typography
- **Hanken Grotesk** (Google Fonts, weights 400/500/600/700/800) — all UI text.
- **IBM Plex Mono** (400/500/600) — labels, captions, codes, axis labels, metric units. Applied via a `.mdp-mono` helper class.
- Headings use `letter-spacing:-0.02em`. Mono labels use `letter-spacing:0.06–0.08em`, uppercase, 9–11px.
- Scale (px): hero numbers 24–26 / 800; section titles 14–19 / 700–800; body 12.5–13; captions 10.5–12; mono micro-labels 8.5–11.

### Radii & shadows
- Radii: controls `7–10px`, cards `11–14px`, modals `18px`, pills/toggles `99px`.
- Active segmented-button shadow: `0 1px 2px rgba(0,0,0,.14)`.
- Modal shadow: `0 24px 60px rgba(0,0,0,.3)`; modal backdrop `rgba(20,22,30,.42)` + `backdrop-filter:blur(3px)`.
- Toggle knob shadow: `0 1px 3px rgba(0,0,0,.35)`.
- Custom scrollbars: 9px, thumb `--track-off` rounded 99px, transparent track.

### Animation
`@keyframes mdpfade`: `opacity 0→1` + `translateY(4px)→0`. Used on detail panel (`.18s`) and modals (`.2s`). Toggle/segment transitions `.15s`.

---

## Screens / Views & Components

### 1. Top bar (66px, `--panel`, bottom border)
- **Logo**: "CareLens" (ink) + " AI" (`#19b1cf` cyan), with a gradient location-pin SVG mark. Sub-label mono 8.5px: `MEDICAL DESERT PLANNER · TRACK 2`. *(In production, swap for your own brand mark.)*
- **Search**: pill input, `--panel-2`, placeholder "Search a state, district or PIN…". Filters the ranked list and, on a state match, sets `focusedState`.
- **Theme toggle**: segmented light/dark, 32×26px buttons; active = `--panel` bg + accent icon.
- **Scenario button**: dot + current scenario name + "SCENARIO" mono tag. Opens scenarios modal.
- **Export plan button**: primary (`--solid` bg, `--solid-ink` text) + watchlist count badge. Opens export modal.

### 2. Left rail (262px, scrollable)
- **CAPABILITY** list — 7 buttons: ICU, Maternity, Emergency, Oncology, Trauma, NICU, Dialysis. Each: colored square dot + label + mono coverage figure (e.g. `0.61`). Active item highlighted. Selecting changes the active capability everywhere (`cap` state).
- **GEOGRAPHIC GRAIN** — segmented control: **State / District / PIN**. Sets `grain`.
- **UNCERTAINTY OVERLAY** — toggle "Hatch data-poor areas" (track turns accent when on). Adds diagonal-hatch texture to low-confidence regions on map + ranked verdict bars.
- **VERDICT LEGEND** — 4 rows (confirmed desert / blind spot / adequately served / unverified) with colored swatch + title + description.
- **Callout** (`--callout-*`): explains the desert-vs-blind-spot logic.

### 3. Center
- **Summary band** — 4 stat cards (one per verdict), each: 3px left accent bar in the verdict color, big 26px count, mono % of total, label.
- **View card** — header has a **Map / Quadrant** segmented tab toggle (left), a contextual title + mono sub (right). Body shows one of:
  - **Map**: choropleth of India (state or district boundaries) colored by the risk gradient; data-poor regions hatched when overlay on; clicking a region selects it. Bottom-left **legend strip**: LOW RISK→HIGH gradient bar + DATA-POOR hatch key, on a frosted `--legend-bg` pill. *(Prototype loads India GeoJSON from a CDN via `d3` + `topojson-client`; has loading + offline-error states. In production, use your own boundary data + mapping lib.)*
  - **Quadrant**: 2×2 scatter, X = **DATA CONFIDENCE →**, Y = **CARE-GAP RISK ↑**. Quadrants tinted + labeled: top-right CONFIRMED DESERTS, top-left BLIND SPOTS · investigate, bottom-right ADEQUATELY SERVED, bottom-left UNVERIFIED · low data. Dashed mid grid lines at the 58 thresholds. Region dots (radius scaled, risk-colored, selected = focus stroke) are clickable; top regions get text labels. Drawn as inline SVG (viewBox 760×460).

### 4. Right panel (396px) — two mutually exclusive states
**A. Ranked list (default)**
- Header: title + mono count; optional accent **focused-state chip** (× to clear); **sort** segmented row (priority / risk / confidence / etc.).
- Rows: rank number (mono) · verdict color bar (hatched if data-poor) · name (ellipsized) + watchlist ★ + note dot · right-aligned big risk number (risk-colored) + mono `CONF nn`. Click selects the region.

**B. Region detail (when a region is selected)**
- "‹ Back to ranking" link. Name + mono sub + verdict pill badge. Optional warn banner if verdict overridden ("reset to model").
- Two metric cards: **CARE-GAP RISK** (big number /100 + risk-colored progress bar) and **DATA CONFIDENCE** (/100 + neutral bar).
- **EVIDENCE LEDGER**: capability label + facility count; a strong/partial/weak proportion bar; counts; then **citation cards** — facility name, STRONG/PARTIAL/WEAK tag pill, italic quote, mono source code (`rec_xxxx · capability/...`).
- **ANALYST OVERRIDE**: 2×2 grid of verdict buttons to manually set the verdict.
- **PLANNER NOTE**: textarea, persisted per region.
- Footer: **watchlist toggle** button (add/remove ★).

### 5. Export modal (560px)
Title "Care-gap action plan" + context line (scenario · capability). Lists watchlisted regions as cards: name + verdict label, mono sub (`RISK · CONF`), an action recommendation, and any planner note (accent chip). Empty state if watchlist empty. Footer: **Close** + **Print / save PDF** (`window.print()`).

### 6. Scenarios modal (460px)
Title "Saved scenarios" + sub. Name input + **Save** (accent) to snapshot current capability/grain/overlay. List of saved scenarios: name + mono desc, **Load** button, × delete. Empty state when none.

---

## Interactions & Behavior
- **Capability / grain / overlay / sort** changes recompute all metrics and repaint map, quadrant, list, summary.
- **Select region** (map dot, quadrant dot, or list row) → right panel switches to detail; map/quadrant highlight the selection with a focus stroke.
- **Search** filters the ranked list; an exact-ish state match sets `focusedState` (chip shown, list scoped to that state).
- **Override**: sets `overrides[regionName]`; verdict badge + bars reflect it; warn banner offers reset.
- **Watchlist**: toggles membership; star appears in list; export count badge updates.
- **Note**: persisted per region; note dot appears in list.
- **Scenarios**: save/load/delete named snapshots.
- **Theme**: light/dark toggle, persisted; map repaints with theme-appropriate strokes.
- **Modals**: click backdrop or Close to dismiss (inner click stops propagation).
- **Print**: export modal "Print / save PDF" calls the browser print dialog.

## State Management
Single component state in the prototype. Key fields:
- `cap` (active capability id) · `grain` (`state`|`district`|`pin`) · `overlay` (bool) · `sort` · `tab` (`map`|`quadrant`)
- `sel` (selected region object, or null) · `query` · `focusedState`
- `showExport`, `showScenarios`, `newScenario`
- **Persisted to `localStorage`** (key `mdp_planner_v1`): `watch` (array of names), `notes` (map name→text), `overrides` (map name→verdict), `scenarios` (array), `scenarioName`, `theme`.

In production, split into UI state (filters/selection/modals) vs. persisted user data (watchlist/notes/overrides/scenarios → your backend or local store), and fetch region metrics + evidence from your real data API rather than the deterministic generator.

## Data model (replace synthetic generator)
Each **region** needs: `name`, `state`, `sub`, `isDist`, and per-capability: `risk` (0–100), `conf`/confidence (0–100), `verdict` (derived: thresholds at 58), facility counts (`strong`/`partial`/`weak`), and an **evidence** array of `{ facility, quote, tag (STRONG|PARTIAL|WEAK), source }`. Capabilities carry an id, label, and coverage figure. The prototype fabricates all of this deterministically from string hashes — see `_metrics`, `_verdict`, `_evidence`, `_decorate` in the logic class for the exact shape and the priority sort weighting (`risk × {desert 2.1, blind 1.5, served 0.7, unknown 1.0}`).

## Assets
- **Fonts**: Hanken Grotesk + IBM Plex Mono (Google Fonts).
- **Map data**: India GeoJSON fetched at runtime from `udit-001/india-maps-data` (CDN). Replace with your own boundary source.
- **Libraries**: `d3` v7 + `topojson-client` v3 (map only). Logo is an inline SVG (replace with your brand).
- No raster images.

## Files
- `Medical Desert Planner.dc.html` — the full prototype (markup + logic). Read the `<script type="text/x-dc">` block for all data generation, metric math, verdict logic, and map drawing.
- `support.js` — the prototype's custom runtime. **Reference only — do not port.** It explains how the `<sc-for>`/`<sc-if>`/`{{ }}` templates resolve, nothing more.

> To preview the original: open `Medical Desert Planner.dc.html` in a browser (needs internet for fonts + map data).
