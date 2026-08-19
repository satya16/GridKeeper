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
(`connections.py::ConnectionRegistry`, module-level singleton
`connections` — deliberately *not* named `hub` despite living in the hub
app, to avoid exactly the confusion an earlier version of this note had:
it's a connection registry, a generic pattern name, unrelated to the
hub/node role rename even though both use similar words), and serves
the REST API + dashboard HTML for the admin.

Auth is intentionally minimal for v1: a single shared admin password,
checked at `POST /api/login` and tracked via an in-memory session
cookie (`auth.py::require_session`/`create_session`) that every other
`/api/*` route and nothing else requires; nodes authenticate their
WebSocket with a per-node bearer token minted at enrollment (see
[pairing](pairing.md)). No multi-user/RBAC — see `_docs/REQUIREMENTS.md`
§2 (Non-goals) and §9 (Security).

**Switched off HTTP Basic 2026-08-19** (was `auth.py::require_admin`):
a real user reported Firefox Focus never showing Basic Auth's native
credential prompt at all — the request just came back "unauthenticated"
with no way to enter a password, since browsers own that UI entirely and
apparently some don't render it. `GET /` now serves the dashboard HTML
unconditionally (the login form is part of the React app itself, so the
bundle has to be reachable before anyone's logged in for that form to
even render) — every `/api/*` route underneath it still requires a
valid session. Sessions are in-memory only (`auth.py`'s `_sessions`
dict, 7-day TTL) — a hub restart logs everyone out, an accepted tradeoff
given this app's size (unlike node bearer tokens, which *are*
persisted, since nodes reconnect unattended and can't re-enter a
password themselves).

Runs via `uvicorn app.main:app`, no systemd unit of its own yet (the
node has one, the hub doesn't — open item, `_docs/REQUIREMENTS.md`
§10). Can run on the same machine as a node it manages — see
`_docs/REQUIREMENTS.md` §3.

**Verified** (2026-08-11, local smoke test): boots cleanly including the
mDNS discovery registry startup/shutdown hooks; `/`, `/api/nodes`,
`/api/discovery`, `/api/metrics`, and static assets all serve correctly;
dashboard HTML renders the expected element structure.

**Session login re-verified live 2026-08-19** against the real published
`satya16dev/grid-hub` Docker image, not just the pytest suite: `GET /`
reachable with no session, `/api/nodes` 401s without one, wrong password
rejected, correct password sets a cookie that then authorizes
subsequent requests, logout clears it and `/api/nodes` 401s again —
confirmed with curl's cookie jar against the actual running container.
Real browser rendering of the new login form is unverified (no Chrome
extension connected this session).
