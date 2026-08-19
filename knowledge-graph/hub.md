---
id: hub
type: component
status: implemented-verified
files:
  - hub/app/main.py
  - hub/app/auth.py
  - hub/app/connections.py
  - hub/app/deps.py
relates_to: [node, pairing, scheduling, metrics, dashboard-ui, data-model, wire-protocol, testing, credentials]
---

The FastAPI app (GridKeeper's hub) — the "one dashboard" side of the
system. Accepts node WebSocket connections at `/ws/node`
(`main.py::node_ws`), tracks which are currently online in memory
(`connections.py::ConnectionRegistry`, module-level singleton `hub` —
note this is a *different* "hub" than the app-level one; it's the
connection registry, named before the hub/node rename existed),
and serves the REST API + dashboard HTML for the admin.

Auth is intentionally minimal for v1: a single shared admin password via
HTTP Basic (`auth.py::require_admin`) gates the dashboard and REST API;
nodes authenticate their WebSocket with a per-node bearer token
minted at enrollment (see [pairing](pairing.md)). No multi-user/RBAC —
see `docs/REQUIREMENTS.md` §2 (Non-goals) and §9 (Security).

Runs via `uvicorn app.main:app`, no systemd unit of its own yet (the
node has one, the hub doesn't — open item, `docs/REQUIREMENTS.md`
§10). Can run on the same machine as a node it manages — see
`docs/REQUIREMENTS.md` §3.

**Verified** (2026-08-11, local smoke test): boots cleanly including the
mDNS discovery registry startup/shutdown hooks; auth gate returns 401
unauthenticated / 200 with credentials; `/`, `/api/nodes`,
`/api/discovery`, `/api/metrics`, and static assets all serve correctly;
dashboard HTML renders the expected element structure.
