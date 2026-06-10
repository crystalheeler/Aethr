# ÆTHR UI Implementation Plan

**Scope: UI reskin of the iNTERCEPT fork only.** Build in order; each phase has acceptance criteria.
Verify visually against the running app before moving on — iterate with evidence, don't batch-lock.

**Out of scope — do NOT implement:** deployment / agent control / MQTT / packaging / mobile,
database & schema, Analysis-mode internals, auth/login changes, and anything marked
"PENDING DECISION" below. If a task seems to need one of these, stop and ask.

The full UI spec is `docs/SkyNet-UIChanges.md`. This plan is the build order.

---

## Phase 1 — ÆTHR title bar  (reference implementation provided)

Replace iNTERCEPT's text-logo header with the layered ÆTHR title bar.

- **Assets** (`static/img/aethr/`): `aethr-bg-tile.png` (seamless wave field),
  `aethr-emblem.png` (transparent raven), `aethr-wordmark.png` (transparent "ÆTHR — AIRCRAFT").
- **CSS**: `static/css/aethr-titlebar.css` (provided). Link it in the base layout (or each
  dashboard template's `<head>` if there's no shared base).
- **Markup**: in the header (`<header class="header">` containing `<div class="logo">`), add the
  `ae-header` class to the header and replace the `.logo` contents per
  `docs/aethr-header-snippet.html`. Keep the right-side device/agent selector (`.status-bar`).
  Do **not** move the nav — it stays as its own row below (`{% include 'partials/nav.html' %}`).
  Note: the header may be inline in each mode template rather than a shared partial — locate it and
  apply the change consistently everywhere it appears.
- **Behavior**: bar height **45px**; background tile `repeat-x`, `background-size: auto 100%` (one
  continuous field, no seams). Never stretch the wide banner image; never re-roll the wave phase.
- **Mode word**: the wordmark asset has "AIRCRAFT" baked in. To swap per mode
  (VESSELS / APRS / RADIOSONDE / DRONES / GPS) pick ONE approach and match it visually to the
  approved Aircraft bar before locking:
  (a) per-mode wordmark images `aethr-wordmark-<mode>.png`, or
  (b) render the lockup as live text (ÆTHR in JetBrains Mono gradient + dash + mode `<span>`),
      bundling JetBrains Mono as a webfont so it renders consistently.

**Acceptance:** every mode shows the 45px layered bar with continuous waves edge-to-edge, correct
emblem + ÆTHR gradient + teal glow, the correct mode word, the device selector on the right, and the
nav row unchanged below.

---

## Phase 2 — Top navigation + menus

- **Nav order:** `SKYNET | SIGNALS | TRACKING | SPACE | WIFI/BT | INTEL | COMMS | AGENTS`.
  No SYSTEM menu (system health → heartbeat icon in the right cluster). TSCM stays under INTEL.
- **Right icon cluster (in order):** clock, layout-sidebar, LEAN, moon, world, database, settings,
  volume, file-text, keyboard, heartbeat (system health), help, logout.
- **Menu contents:**
  - TRACKING: Aircraft, Vessels, Radiosonde, APRS, GPS, Drones, WiFi (placeholder/SOON),
    Bluetooth (placeholder/SOON)
  - COMMS: Meshtastic, Mesh Core
  - WIFI/BT: BT Locate, WiFi Locate
  - INTEL: TSCM, Spy Stations, WebSDR, Analysis
  - SPACE / SIGNALS: unchanged from iNTERCEPT
- **Widget width:** 1100px.

**Acceptance:** nav order and menu contents match exactly; Drones lives under TRACKING (not INTEL);
no SYSTEM menu; the right cluster matches the listed order.

---

## Phase 3 — Standalone full-page dashboard model

Every signal mode is a standalone full-page dashboard like Aircraft/Vessels: full-bleed
Leaflet/CARTO map as the page background, a stats strip on top, panels floating over the map, and a
controls bar along the bottom. Rebuild **APRS, Radiosonde, and Drones** onto this model (they are
currently the embedded-card SPA layout). Do **not** bolt CSS hacks onto the card view — use the real
dashboard page structure. Change each mode from its own template/JS; do not copy Aircraft's panels
onto another mode.

**Acceptance:** APRS, Radiosonde, and Drones each render full-bleed (map fills the page) with their
own real content, matching the per-mode rules in UIChanges § 1.10.

---

## Phase 4 — Tab & menu interaction model

- Left menus (e.g. Config, Agents) are grid columns that **push the map** when open — never float.
- Tabs are fixed edge overlays with rounded corners facing **inward**; an open menu's tab rides the
  panel's right edge.
- Collapsed: the map fills fully and the zoom +/- controls ride the map edge.
- The map-only (declutter) button highlights **only when active**.

**Acceptance:** opening a left menu pushes the map; tabs face inward and ride the open panel edge;
the collapsed state fills the map; the map-only button highlights only when active.

---

## Phase 5 — Per-mode behavior  (UIChanges § 1.10)

- **Aircraft:** baseline. Left-edge tabs: AGENTS, ACARS, VDL2. No Config tab.
- **Vessels:** mirrors Aircraft. Tab: AGENTS. No Config tab.
- **Radiosonde:** left config menu → CONFIG tab (default collapsed); AGENTS tab;
  **no right rail and no right tab.**
- **APRS:** config menu → CONFIG tab; AGENTS tab + STATIONS rail; no tracker bar; no map framing;
  the upper-bar time-ticker becomes a LOG button; Packet Log hidden by default (LOG toggles it).
- **GPS:** completely untouched — apply no ÆTHR rules.
- **Drones:** moved INTEL → TRACKING; remove the "Drone Intelligence" bar; chip stats
  (Contacts / Non-Compliant / High Risk); Contacts = right-side rail collapsible to a tab;
  Config = left tab; no floating Contacts block and no "Selected Contact" panel.

**Acceptance:** each mode matches its rule exactly; GPS behaves identically to upstream.

---

## Phase 6 — Run-state + popout cleanup (UI only)

- Remove iNTERCEPT's "Run State = which mode owns the SDR" indicator — the highlighted active tab IS
  the indicator.
- Any popout shares state with the main app; single-instance per analyst; the original tab stays put
  on whatever mode it was on.

**Acceptance:** no standalone SDR-ownership run-state widget remains; popouts (if kept) share state.

---

## PENDING DECISION — do NOT implement (ask first)

- Per-agent capture-activity indicator (how to surface "capturing on agent X / Y / Z").
- Settings modal placement & contents.
- Notifications / alerts surface (toasts vs bar vs tab).
- Mobile UX.
- Dropping the Aircraft "SKYNET - See the Invisible" tagline — confirm timing.
- Legacy popout dashboards (Aircraft Radar / Vessel Radar / Satellite Tracker): fold into the SPA or
  retire — decide first.
- The emblem must be redrawn as original vector art before any public release (use the provided
  asset as-is for now).
