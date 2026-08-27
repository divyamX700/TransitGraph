# ADR-0006: TransitGraph — Complete Frontend Design Philosophy

## Status
Accepted

## Date
2026-08-08

---

## 1. Design Name & Identity

**"The Departure Board"** — a dark utility interface where the map and data are the product. Everything else recedes.

Product name: **TransitGraph**. Short, technical, memorable. Signals graphs, data, and transit simultaneously. CV-ready.

---

## 2. Core Aesthetic Philosophy

This is not a consumer app. This is a tool — closer to a Bloomberg terminal or a railway departure board than a Google Maps clone.

**Rules:**
- **Dark always.** No light mode. No section-level theme flips. `#0C0E13` base, never warm paper or cream.
- **Monochrome structure.** Every surface, border, label and icon uses grayscale CSS tokens only.
- **Transit line colors are the only saturated hues on screen.** They must stand out because they carry real meaning — they represent actual physical train lines. Using them for anything else (buttons, accents, decorations) dilutes their signal.
- **No AI slop.** No purple gradients, no generic glassmorphism on everything, no AI-mesh hero backgrounds, no Inter + slate-900 defaults.
- **Utility over decoration.** Every visual element earns its place. If it doesn't communicate something true, it's removed.

---

## 3. Design Tokens (Canonical Source of Truth)

All values are defined in `web/src/index.css` as CSS custom properties. **Never hard-code hex values directly in components.**

### Surfaces
| Token | Value | Use |
|---|---|---|
| `--bg-primary` | `#0C0E13` | App background, nav |
| `--bg-elevated` | `#151820` | Cards, panels |
| `--bg-input` | `#1C2030` | Input fields |
| `--bg-hover` | `#1F2438` | Hover states, active items |

### Text
| Token | Value | Use |
|---|---|---|
| `--text-primary` | `#E8ECF4` | Headings, important labels |
| `--text-secondary` | `#7B839A` | Body text, descriptions |
| `--text-muted` | `#4A5068` | Hints, timestamps, metadata |

### Borders
| Token | Value | Use |
|---|---|---|
| `--border` | `#252A3A` | Default dividers, card edges |
| `--border-light` | `#2E3448` | Subtle separators within panels |

### Transit Line Colors (Only Saturated Hues — Handle With Care)
| Token | Value | Line |
|---|---|---|
| `--line-western` | `#2563EB` | Western Railway (WR_MAIN) |
| `--line-central` | `#DC2626` | Central Railway Main (CR_MAIN) |
| `--line-harbour` | `#0891B2` | Harbour Line (CR_HARBOUR) |
| `--line-trans` | `#7C3AED` | Trans-Harbour (CR_TRANS) |
| `--line-port` | `#059669` | Port / Uran Line (CR_PORT) |
| `--line-dahanu` | `#2563EB` | Dahanu Road (WR_DAHANU, shares Western color) |

**Rule:** These tokens may only be used to color train line polylines, station dots, interchange markers, and line badge chips. Never use them as UI accent colors (button backgrounds, focus rings, etc.).

### Semantic
| Token | Value | Use |
|---|---|---|
| `--error` | `#DC2626` | Errors (matches Central line — acceptable collision) |
| `--success` | `#059669` | Success (matches Port line — acceptable collision) |
| `--warning` | `#D97706` | Warnings |

### Spacing Scale
`4 / 8 / 12 / 16 / 20 / 24 / 32px` — use `--space-N` tokens.

### Radius Scale
`6px (sm) / 10px (md) / 14px (lg) / 9999px (pill)` — **one system, no ad-hoc border-radius values**.

---

## 4. Typography

### Typefaces
- **Display / UI:** `Geist` (300, 400, 500, 600, 700)
- **Monospace / data:** `Geist Mono` (400, 500) — used for times, station IDs, train numbers, metadata

### Rules
- **Never use `Inter`** unless the user explicitly asks for it. It is the LLM default.
- Geist is deliberately chosen: sharp, modern, slightly condensed feel — suits the data-dense utility aesthetic.
- Geist Mono for anything that represents timetable data — departure times, arrival times, train numbers. This signals "precise system data" vs "interface chrome".
- **No serifs.** Not editorial enough to warrant it.
- Font size scale: `11px (labels/eyebrows) / 12px (mono data) / 13px (captions) / 15px (inputs) / base 16px / 18px (card titles) / 24px (section headings)`.

---

## 5. Layout Philosophy

### Overall Structure
- **Two-panel split**: fixed-width left panel (380px) for search + results; full-height right panel for the map.
- The map is the product. The left panel is the control surface. Never let the panel compete with the map for visual weight.
- **No hero sections, no landing page patterns.** This is a tool, not a marketing page.

### Spacing Discipline
- Interior padding: `--space-5` (20px) for sections, `--space-3` (12px) for items.
- Never use padding as a design substitute for whitespace — the dark background provides natural breathing room.

### Responsive
- Mobile: panel stacks on top of map (`grid-template-rows: auto 50dvh`). No horizontal split.
- Desktop: `grid-template-columns: 380px 1fr`.
- Always use `100dvh` (not `100vh`) to handle mobile browser chrome correctly.

---

## 6. Component Rules

### Navigation
- Height: `60px` (`--nav-height`).
- Left: wordmark (`TransitGraph`) with a multi-dot logo — one dot per major line color (Western blue, Central red, Harbour cyan). Subtle, memorable.
- Right: small metadata text ("Mumbai Suburban Railway") in `--text-muted`. No buttons, no CTAs.

### Station Inputs
- Filled style with `--bg-input` background.
- Focus ring uses `--line-western` (Western blue) — the one exception to the transit-color-only rule, justified because it is a subtle focus indicator, not a branding element.
- Autocomplete dropdown: `--bg-elevated` with `1px solid --border`. Active item uses `--bg-hover`.
- Keyboard navigation: Arrow Up/Down, Enter to select, Escape to close.

### Route Cards
- Dark surface (`--bg-elevated`), `1px solid --border`, `--radius-md`.
- Hover state: subtle border brightens to `--border-light`.
- Selected/active state: `1px solid` the dominant line color of the route (e.g. Western blue for a Western line journey).
- Contains: origin, destination, line badge chips, departure/arrival times, duration pill.

### Line Badge Chips
- Small, pill-shaped chips with the line's color as background.
- Text must have sufficient contrast against the line color (use white text).
- Size: compact — `11px font, 4px 8px padding`.

### Station Dots on Map
- **Source / Destination:** Filled circle in the relevant line color, white ring outline. Size: 10px.
- **Interchange station:** SVG split circle — left half in line 1 color, right half in line 2 color. White ring outline. Size: 14px.

### Map Polylines
- **Background network lines (not in active route):** rendered but hidden (`display: none` or fully transparent) when a route is selected. 0% visibility on unused lines — no fading.
- **Active route lines:** full opacity at the line's canonical color, 4px stroke weight.
- **Slicing:** index-based slicing (not Turf's `lineSlice`). Snap to nearest coordinate in the shape array. This is more robust at busy interchange nodes like Dadar.

### Skeleton Loaders
- Shape must match the final layout's geometry. No generic circular spinners.
- Use CSS animation `shimmer` keyframe (left-to-right gradient sweep).

### Duration Pill
- Displayed between departure and arrival times on the route card.
- Style: pill badge, `--bg-hover` background, `--text-secondary` text, `--radius-pill`.

---

## 7. Interaction Philosophy

- **Micro-animations yes, gratuitous animations no.** Every animation must communicate something: loading state, selection state, hover affordance.
- **Hover states:** subtle background shift (`--bg-hover`). No color explosions.
- **Active state on buttons:** `scale(0.97)` to simulate physical press.
- **Transitions:** `150ms ease` for background/border changes. Nothing slower for interactive elements.
- **No perpetual looping animations** except skeleton shimmer.

---

## 8. Anti-Patterns (Explicitly Banned)

| Pattern | Reason |
|---|---|
| AI purple/blue gradient backgrounds | Generic LLM default |
| Generic glassmorphism on panels | Unmotivated, slop |
| Using transit line colors as general UI accent | Dilutes map signal |
| `Inter` font as default | Generic LLM default |
| Warm beige/cream backgrounds | Wrong aesthetic family |
| Plain `100vh` | Breaks on mobile browser chrome |
| Inline hard-coded hex values | Bypasses design token system |
| Empty skeleton cells | Broken layout |
| Numbered section eyebrows (01 / 02) | Not a sequenced document |
| Emoji in UI | Not appropriate for utility tool |
| Light mode sections interspersed with dark | Theme coherence violation |

---

## 9. Design Dials (from `design-taste-frontend` vocabulary)

For this product specifically:
- `DESIGN_VARIANCE: 4` — deliberate, disciplined, not artsy
- `MOTION_INTENSITY: 3` — functional micro-interactions only
- `VISUAL_DENSITY: 7` — this is a data tool; density is a feature

---

## 10. Future Polish Checklist

When implementing future UI changes, verify:
- [ ] All colors sourced from CSS tokens, no hard-coded hex
- [ ] No saturated color used outside transit line context
- [ ] Keyboard navigation preserved
- [ ] Skeleton loader shape matches final layout
- [ ] Active/hover/error/empty states all implemented
- [ ] `100dvh` used instead of `100vh`
- [ ] Font exclusively Geist / Geist Mono
- [ ] New component radius uses existing scale values only

