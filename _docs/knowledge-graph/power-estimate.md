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

Rough whole-system power draw estimate and electricity-cost calculator.
Not a measured reading — no RAPL/hardware sensor support (too
inconsistent across the mixed lab hardware this project targets).
`node/grid_node/power.py::estimate_watts()` is a pure linear
interpolation between a node's configured `idle_watts`/`max_watts`
(`config.py`, generic desktop-class defaults: 40W idle / 150W max),
scaled by the `cpu_percent` metric [metrics](metrics.md) already
collects. It rides along the same `metrics` wire-message field as
`estimated_watts` — no new protocol, no schema change — and
`metrics_store.py::record()` was the one required hub-side change (it
explicitly whitelists keys per point).

The dashboard's **Power** tab (`PowerSection.jsx`, wired into `App.jsx`'s
nav) reuses the existing `/api/metrics` polling path — no new endpoint.
It sums the latest `estimated_watts` across currently-online nodes and
projects daily/weekly/monthly kWh and cost against a user-entered
cost-per-kWh, plus a per-node breakdown table. A currency picker (5
common currencies + free-text "Other") replaces a hardcoded `$`. A
what-if scratchpad lets the user exclude specific real nodes and/or add
hypothetical machines at a flat user-supplied wattage (no CPU-scaling —
there's no real usage to scale from) to see the projection for a
different fleet size. Cost, currency, and what-if state all persist to
browser `localStorage`; no backend user-preferences mechanism exists in
this codebase to hook into instead. The "Live metrics" charts
([metrics](metrics.md)'s `MetricsSection.jsx`) also gained a fourth
"Estimated power" chart for free, since its chart list is a generic
array.

**Verified** (real end-to-end smoke test, not just pytest): a real
`grid-node` enrolled against a locally-run hub reported real
`cpu_percent` -> `estimated_watts` over the actual WebSocket, matching
the formula exactly; the dashboard's Power tab (via Playwright, real
Chromium) showed the live node in its per-node breakdown, correct cost
math, currency switching, and what-if scenario math (excluding a real
node, adding hypothetical machines), all surviving a page reload.
