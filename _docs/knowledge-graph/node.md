---
id: node
type: component
status: implemented-verified
files:
  - node/grid_node/daemon.py
  - node/grid_node/config.py
  - node/grid_node/__main__.py
relates_to: [hub, pairing, scheduling, metrics, boinc-backend, fah-backend, wire-protocol, testing, node-local-ui, power-estimate]
---

The per-machine daemon (`grid-node`) that runs on each compute machine.
Detects which backends are present ([boinc-backend](boinc-backend.md),
[fah-backend](fah-backend.md)) at startup, then runs three
concurrent loops from `daemon.py::run()`:

- `_status_loop` — polls backend status + [metrics](metrics.md) and sends
  it to the hub every `poll_interval_seconds` (default 10s).
- `_command_loop` — reads incoming WebSocket frames (commands, schedule
  policy updates) and dispatches them.
- `_fah_schedule_loop` — only started if FAH is active; runs
  independently of the WebSocket connection lifecycle (see
  [scheduling](scheduling.md) for why).

If `config.local_ui_enabled`, `run()` also starts
[node-local-ui](node-local-ui.md)'s HTTP server, and `_status_loop`
feeds it the same status/metrics data it sends to the hub each poll.
Off by default.

If unconfigured, `grid-node run` enters pairing mode automatically
instead of failing — see [pairing](pairing.md). Reconnects to the hub
with exponential backoff on any drop; `poll_interval_seconds` also
doubles as the heartbeat cadence, no separate heartbeat frame.

Config lives at `~/.config/grid-node/config.toml` (mode 600, holds the
bearer token) — see `node/grid_node/config.py`.

**Verified** (2026-08-11, local smoke test): `_status_loop` and
`_command_loop` confirmed working against a real hub (no BOINC/FAH
installed in the test environment, so `_fah_schedule_loop` and both
backends' actual command execution remain unverified beyond their error
paths — see [boinc-backend](boinc-backend.md)/[fah-backend](fah-backend.md)).
Restart-and-reconnect using only the saved config (no re-enroll) confirmed
working, including immediate schedule re-sync on reconnect.
