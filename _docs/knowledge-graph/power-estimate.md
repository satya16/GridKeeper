---
id: power-estimate
type: component
status: implemented-verified
files:
  - node/grid_node/power.py
  - node/grid_node/config.py
  - hub/app/metrics_store.py
  - hub/frontend/src/components/PowerSection.jsx
relates_to: [metrics, node, hub, dashboard-ui]
---

Rough whole-system power draw estimate and electricity-cost calculator,
added 2026-08-21. Not a measured reading — no RAPL/hardware sensor
support (too inconsistent across the mixed lab hardware this project
targets). `node/grid_node/power.py::estimate_watts()` is a pure linear
interpolation between a node's configured `idle_watts`/`max_watts`
(`config.py`, generic desktop-class defaults: 40W idle / 150W max),
scaled by the `cpu_percent` metric [metrics](metrics.md) already
collects. It rides along the same `metrics` wire-message field as
`estimated_watts` — no new protocol, no schema change — and
`metrics_store.py::record()` was the one required hub-side change (it
explicitly whitelists keys per point).

The dashboard's **Power → Calculator** tab (`PowerSection.jsx`, wired
into `App.jsx`'s nav) reuses the existing `/api/metrics` polling path —
no new endpoint. It sums the latest `estimated_watts` across
currently-online nodes, lets the user enter a cost-per-kWh (persisted to
browser `localStorage`; no backend user-preferences mechanism exists in
this codebase to hook into instead), and projects daily/weekly/monthly
kWh and cost, plus a per-node breakdown table. The existing "Live
metrics" charts ([metrics](metrics.md)'s `MetricsSection.jsx`) also gained
a fourth "Estimated power" chart for free, since its chart list is a
generic array.

**Verified 2026-08-21** (real end-to-end smoke test, not just pytest): a
real `grid-node` enrolled against a locally-run hub reported
`cpu_percent: 2.3` -> `estimated_watts: 42.53` over the actual
WebSocket, matching the formula exactly; the dashboard's Power ->
Calculator tab (via Playwright, real Chromium) showed the live node in
its per-node breakdown, correct daily/weekly/monthly cost math for a
given cost-per-kWh, and the Metrics tab's new fourth "Estimated power"
chart rendered real data alongside CPU/RAM/temp. No console errors
beyond a benign pre-login 401 (expected — `checkSession` fires before
any cookie exists).
