---
id: manager
type: component
status: implemented-verified
files:
  - manager/app/main.py
  - manager/app/auth.py
  - manager/app/ws_manager.py
  - manager/app/deps.py
relates_to: [worker, pairing, scheduling, metrics, dashboard-ui, data-model, wire-protocol, testing]
---

The FastAPI app (`grid-manager`) — the "one dashboard" side of the
system. Accepts worker WebSocket connections at `/ws/worker`
(`main.py::worker_ws`), tracks which are currently online in memory
(`ws_manager.py::ConnectionManager`, module-level singleton `manager` —
note this is a *different* "manager" than the app-level one; it's the
connection registry, named before the manager/worker rename existed),
and serves the REST API + dashboard HTML for the admin.

Auth is intentionally minimal for v1: a single shared admin password via
HTTP Basic (`auth.py::require_admin`) gates the dashboard and REST API;
workers authenticate their WebSocket with a per-worker bearer token
minted at enrollment (see [pairing](pairing.md)). No multi-user/RBAC —
see `docs/REQUIREMENTS.md` §2 (Non-goals) and §9 (Security).

Runs via `uvicorn app.main:app`, no systemd unit of its own yet (the
worker has one, the manager doesn't — open item, `docs/REQUIREMENTS.md`
§10). Can run on the same machine as a worker it manages — see
`docs/REQUIREMENTS.md` §3.

**Verified** (2026-08-11, local smoke test): boots cleanly including the
mDNS discovery registry startup/shutdown hooks; auth gate returns 401
unauthenticated / 200 with credentials; `/`, `/api/workers`,
`/api/discovery`, `/api/metrics`, and static assets all serve correctly;
dashboard HTML renders the expected element structure.
