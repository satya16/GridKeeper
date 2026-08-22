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

**Verified** (2026-08-11, local smoke test): the full data pipeline —
`psutil` collection on the node, `metrics.py`'s temperature sensor
lookup (found a real sensor on the test machine and returned a plausible
value), the rolling-window store, and `GET /api/metrics` — confirmed
working with real, sane-looking values (e.g. `cpu_percent: 8.5`,
`temperature_c: 49.375`).

**2026-08-21**: the `metrics` block gained a fourth field,
`estimated_watts` — a rough power-draw estimate, not a hardware reading.
See [power-estimate](power-estimate.md) for the estimation model and the
new Power → Calculator dashboard tab; `MetricsSection.jsx`'s existing
chart list picked it up as a fourth "Estimated power" chart for free.

**Chart rendering + interactivity verified 2026-08-18**, once the
dashboard moved to React ([dashboard-ui](dashboard-ui.md)) and real
browser testing became possible via Playwright: `LineChart.jsx` (the
port of the old hand-rolled SVG chart code) renders real CPU/RAM/temp
data correctly, the device filter pills work, and the hover
crosshair+tooltip genuinely fires with correct content — confirmed via
direct pointer-event/computed-style inspection after an initial
Playwright-automation false negative (a frozen synthetic mouse loses
hover after a late incidental layout shift; irrelevant to a real user's
continuously-moving mouse). The categorical palette
(`MetricsSection.jsx`'s `CATEGORICAL_COLORS`) re-passed the `dataviz`
skill's `validate_palette.js` unchanged from the original vanilla-JS
version. No remaining unverified piece for this entity.
