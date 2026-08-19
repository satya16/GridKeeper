---
id: wire-protocol
type: protocol
status: implemented-verified
files:
  - hub/app/schemas.py
  - hub/app/main.py
  - node/grid_node/daemon.py
relates_to: [hub, node, scheduling, metrics, data-model]
---

The JSON frame protocol over the `/ws/node` WebSocket, once a node is
authenticated (bearer token in the connection query string — see
[pairing](pairing.md)). Full frame list documented as a comment block at
the bottom of `hub/app/schemas.py`; summary:

**node → hub:**
- `{"type": "status", "backends": {...}, "metrics": {...}}` — sent every
  `poll_interval_seconds`; `backends` feeds `last_status_json`, `metrics`
  feeds the [metrics](metrics.md) rolling window.
- `{"type": "command_result", "command_id", "status", "result"}` —
  correlates back to a REST-issued command via `command_id`.

**hub → node:**
- `{"type": "command", "command_id", "backend", "action", "payload"}` —
  issued from `POST /api/nodes/{id}/commands`; the hub holds the
  HTTP request open (via an `asyncio.Future` keyed by `command_id`,
  `connections.py`) until the result frame arrives or a 15s timeout hits.
- `{"type": "schedule", "policy": {...}}` — pushed on every successful
  connect (not just when the policy changes), so a reconnecting node
  always converges to the hub's current policy — see
  [scheduling](scheduling.md).

No protocol versioning yet — both ends are the same codebase deployed
together, so this hasn't mattered. Would need a `type` fallback/ignore
path (already present — unknown frame types are logged and skipped, not
fatal) before node and hub could safely run different versions.

**Verified** (2026-08-11, local smoke test): all four frame types
exchanged successfully in a live run — `status` (with real `psutil`
metrics), `command`/`command_result` (round-tripped through a REST call
that held open until the result arrived, including a realistic error
case), and `schedule` (received on both initial connect and reconnect).

