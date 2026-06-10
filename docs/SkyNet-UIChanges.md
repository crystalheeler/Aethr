# SkyNet UI Changes

*Companion to: SkyNet vs iNTERCEPT — Change Summary. Scope: UI changes that are not specific to Analysis mode. For Analysis-specific UI, see AnalysisImpl.*

> **Updated after the Aethr-2 session.** Adds the ÆTHR branding/title bar (§ 1.7), the standalone full-page dashboard model (§ 1.8), the tab/menu interaction model (§ 1.9), the top-nav structure (§ 1.5), menu contents (§ 1.6), and per-mode behavior (§ 1.10). The project is now branded **ÆTHR** (Æ "ash" ligature); "SkyNet" persists in filenames and legacy references.

## 1. Design Decisions

Locked-in decisions about the ÆTHR UI outside of Analysis mode.

### 1.1 Layout shell

- Tabbed mode-selector layout: kept
- Flask templates, dark theme, SSE/WebSocket, Leaflet: kept
- All iNTERCEPT decoder agents kept (dump1090, rtl_433, AIS-catcher, acarsdec, dumpvdl2, multimon-ng, SatDump, direwolf, aircrack-ng, bleak)
- Every signal mode now renders as a standalone full-page dashboard (see § 1.8) — not iNTERCEPT's embedded-card SPA
- The shell's top row is the ÆTHR title bar (§ 1.7); the mode-selector nav is a separate row beneath it (§ 1.5)

### 1.2 Authentication & identity (unchanged)

- App-level password authentication removed — overlay network handles identity
- Multi-user analyst identity: edits in Analysis mode are attributed (see AnalysisImpl § 1.3)

### 1.3 Run state / mode indicator (unchanged)

- iNTERCEPT's "Run State = which mode owns the SDR" semantic removed — a fleet of agents invalidates that meaning
- The Active Mode Indicator (highlighted tab) remains the visual indicator of which mode you're in
- The live-vs-analysis distinction needs no separate indicator — the selected tab IS the indicator
- Per-agent capture-activity status takes the place of the old single-SDR Run State (design pending — see § 2.3)

### 1.4 Popout behavior (unchanged)

- Popout-as-isolated-dashboard pattern removed — any popouts ÆTHR keeps must share state with the main app
- General popout rule: single-instance per analyst; original tab stays put on whatever mode it was on
- Analysis mode uses this popout pattern (see AnalysisImpl § 1.2)

### 1.5 Top navigation structure (NEW — locked)

- Top nav order: **SKYNET | SIGNALS | TRACKING | SPACE | WIFI/BT | INTEL | COMMS | AGENTS**
- No SYSTEM menu — system health moved to the heartbeat icon in the right cluster. TSCM stays under INTEL, not at top level.
- Right icon cluster, in order: clock · layout-sidebar · LEAN · moon · world · database · settings · volume · file-text · keyboard · heartbeat (system health) · help · logout
- Widget width: 1100px
- The nav is its own row beneath the ÆTHR title bar — menus are never placed inside the title bar (see § 1.7)

### 1.6 Menu contents (NEW — locked)

- **TRACKING:** Aircraft, Vessels, Radiosonde, APRS, GPS, Drones, WiFi (placeholder), Bluetooth (placeholder)
- **COMMS:** Meshtastic, Mesh Core
- **WIFI/BT:** BT Locate, WiFi Locate
- **INTEL:** TSCM, Spy Stations, WebSDR, Analysis — (Drones moved out to Tracking)
- **SPACE / SIGNALS:** unchanged from iNTERCEPT

### 1.7 ÆTHR title bar (NEW — locked, 45px)

- The title bar is **layered, not a single baked banner** — a fixed-aspect banner can't fill a wide title bar without warping
- **Background:** the seamless wave-field tile (`aethr-bg-tile.png`) set `background-repeat: repeat-x`, `background-size: auto 100%` — one continuous sinefield + matrix-rain texture across the full window width, with no visible tile seams
- **Left lockup, floated on top:** the transparent raven emblem + the ÆTHR wordmark (ÆTHR in JetBrains Mono with the green→teal→blue→purple gradient; muted dash; mode word in `#cfe9e7`) + a teal drop-shadow glow
- **Mode word swaps live per mode** (AIRCRAFT → VESSELS → APRS → RADIOSONDE → DRONES → GPS)
- The device/agent selector stays at the right of the bar; the nav is a separate row below
- Hard rules: do not stretch/scale the banner image into the bar; do not re-roll the wave phase between renders
- Assets: `aethr-titlebar-layers.zip`. JetBrains Mono is the accepted wordmark face (the iNTERCEPT-font rebuild was canceled)
- Pending: drop the Aircraft "SKYNET - See the Invisible" tagline during the logo drop-in

### 1.8 Mode view model: standalone full-page dashboards (NEW — locked)

- Every signal mode is a standalone full-page dashboard, structured like Aircraft and Vessels: a full-bleed Leaflet/CARTO map as the page background, a stats strip across the top, panels floating over the map, and a controls bar along the bottom
- This replaces iNTERCEPT's embedded-card SPA layout (a map inside a bordered card inside the content column) — no CSS hacks bolted onto the card view
- APRS, Radiosonde, and Drones were rebuilt onto this model (they were previously embedded-card)

### 1.9 Tab & menu interaction model (NEW — locked)

- Left menus (e.g. Config, Agents) are grid columns that **push the map** when open — they never float over it
- Tabs are fixed edge overlays with rounded corners facing **inward**; when a menu is open, its tab rides the open panel's right edge
- Collapsed: the map fills the viewport fully and the zoom +/- controls ride the map edge
- The map-only (declutter) button highlights **only when actually active**
- The legend sits under the map-only / full-screen buttons (optionally moveable — TBD)

### 1.10 Per-mode behavior (NEW — locked)

- **Aircraft:** baseline. Left-edge tabs: AGENTS, ACARS, VDL2. No Config tab.
- **Vessels:** mirrors Aircraft. Tab: AGENTS. No Config tab.
- **Radiosonde:** standalone dashboard; left config menu collapses to a CONFIG tab (default collapsed); AGENTS tab; **no right rail and no right tab**
- **APRS:** left config menu → CONFIG tab; AGENTS tab + STATIONS rail; no tracker bar; no map framing; the upper-bar time-ticker becomes a LOG button; Packet Log hidden by default (LOG toggles it)
- **GPS:** completely untouched — no ÆTHR rules applied
- **Drones:** renamed from "Drone Intel" and moved from INTEL to TRACKING; the "Drone Intelligence" bar removed; chip stats (Contacts / Non-Compliant / High Risk); Contacts = right-side rail, collapsible to a tab; Config = left tab; no floating Contacts block and no "Selected Contact" panel

### 1.11 Branding / identity (NEW)

- Project branded **ÆTHR** (Æ "ash" ligature); the emblem is the twin-raven (Huginn & Muninn) crest
- Theme follows iNTERCEPT conventions: near-black background, cyan-teal primary, amber accent, monospace typography
- The emblem is currently derived from a commercial-pendant photo and **must be redrawn as original vector art before public release**
- A simplified favicon mark is still needed (the full emblem is too intricate below ~48px)

## 2. Open Questions

Decisions not yet made. Items here are not blocking but need resolution before implementation in that area can complete.

### 2.1 Declutter pass — largely RESOLVED

- The per-mode declutter decisions are now captured as locked behavior in § 1.10 (APRS tracker bar / map framing / time-ticker → LOG / Packet Log; the Drone Intelligence bar; etc.)
- Remaining: confirm there are no further global elements to hide/relocate beyond the per-mode rules

### 2.2 Existing iNTERCEPT popout dashboards

- Aircraft Radar, Vessel Radar, and Satellite Tracker were full-screen popouts that did not share state with the main app
- With every mode now a standalone full-page dashboard (§ 1.8), the decision is still needed: fold these legacy popouts into the SPA or retire them; anything kept must follow the § 1.4 popout rule

### 2.3 Capture-activity indicator (open)

- iNTERCEPT showed which mode owned the single SDR; ÆTHR has many agents capturing in parallel
- How to surface "currently capturing on agent X / Y / Z" — single global indicator, per-agent status row, or dedicated dashboard panel? Closely related to the Agent Fleet Status feature (AnalysisImpl § 2.3)

### 2.4 Settings modal placement (open)

- Where the global settings cog lives in the new UI
- Candidates for what's in it: retention policy, WiGLE import/export, mobile sync prefs, overlay preferences (some items currently listed under Analysis may belong here — see AnalysisImpl § 2.3)

### 2.5 Notifications and alerts (open)

- How are alerts surfaced (drone detected, AoI breach, signal of interest, etc.)?
- Where does the alerts panel live — toasts, persistent bar, dedicated tab?

### 2.6 Mobile UX considerations (open)

- Capacitor Solo offline + Connected webview modes affect what the mobile UI can assume
- Touch targets, panel widths, and popout behavior on mobile are separate considerations from desktop
