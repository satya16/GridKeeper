---
id: hub
type: component
status: implemented-verified
files:
  - hub/app/main.py
  - hub/app/auth.py
  - hub/app/connections.py
  - hub/app/deps.py
relates_to: [node, pairing, scheduling, metrics, dashboard-ui, data-model, wire-protocol, testing, credentials, users-and-roles, power-estimate]
---

The FastAPI app (GridKeeper's hub). Accepts node WebSocket connections at
`/ws/node` (`main.py::node_ws`), tracks which are currently online in
memory (`connections.py::ConnectionRegistry`, singleton `connections` —
a generic connection-tracking name, not a reference to the hub/node role
despite living in the hub app), and serves the REST API + dashboard HTML
for the admin.

Auth: real per-user accounts + roles (session cookie, bcrypt) — see
[users-and-roles](users-and-roles.md) for the full model. Nodes
authenticate their WebSocket separately with a per-node bearer token
minted at enrollment (see [pairing](pairing.md)), unrelated to admin/user
auth. Sessions are in-memory only (7-day TTL) — a hub restart logs
everyone out, an accepted tradeoff at this app's size.

Runs via `uvicorn app.main:app`, no systemd unit of its own yet (the
node has one). Can run on the same machine as a node it manages — see
`_docs/REQUIREMENTS.md` §3.

**Verified**: boots cleanly including the mDNS discovery registry
startup/shutdown hooks; full REST API, static assets, and session login
(wrong/correct password, cookie persistence, logout) confirmed both via
the pytest suite and live against the real deployed Docker image.
