---
id: metrics
type: component
status: implemented-verified
files:
  - node/grid_node/metrics.py
  - hub/app/metrics_store.py
  - hub/app/api/metrics.py
  - hub/frontend/src/components/MetricsSection.jsx
  - hub/frontend/src/components/LineChart.jsx
relates_to: [node, hub, dashboard-ui, wire-protocol, power-estimate]
---

CPU%/RAM%/temperature collection and the "Live metrics" dashboard graphs.
`node/grid_node/metrics.py` collects via `psutil`, riding along in
every status frame (see [wire-protocol](wire-protocol.md)) rather than a
separate channel. `hub/app/metrics_store.py` keeps an in-memory
rolling window per node (~1 hour, `collections.deque`) — deliberately
*not* persisted to SQLite; this is "recent live state," not the
long-term historical analytics `_docs/REQUIREMENTS.md` §2 puts out of
scope.

The dashboard renders three separate line charts (CPU%, RAM%, temp °C —
never one dual-axis chart) with a per-device color assigned from a fixed
8-slot categorical palette, a shared device filter, and a crosshair
tooltip — see `_docs/REQUIREMENTS.md` §8 for the full design rationale
(follows the project's `dataviz` skill). Temperature is effectively
Linux-only (`psutil.sensors_temperatures()` isn't implemented on
macOS/Windows) and degrades to `null` rather than erroring.

**Verified**: the full pipeline — `psutil` collection on the node
(including a real temperature sensor lookup), the rolling-window store,
and `GET /api/metrics` — confirmed working with real, sane-looking
values. Chart rendering/interactivity (`LineChart.jsx`) verified in a
real browser via Playwright: real CPU/RAM/temp data renders correctly,
the device filter pills work, and the hover crosshair/tooltip fires with
correct content. The categorical palette (`MetricsSection.jsx`'s
`CATEGORICAL_COLORS`) passes the `dataviz` skill's `validate_palette.js`.
No remaining unverified piece for this entity.

The `metrics` block also carries a fourth field, `estimated_watts` — a
rough power-draw estimate, not a hardware reading. See
[power-estimate](power-estimate.md) for the estimation model and the
Power → Calculator dashboard tab; `MetricsSection.jsx`'s chart list
picked it up as a fourth "Estimated power" chart for free.
