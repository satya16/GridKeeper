---
id: users-and-roles
type: component
status: implemented-verified
files:
  - hub/app/auth.py
  - hub/app/audit.py
  - hub/app/api/users.py
  - hub/app/api/auth.py
  - hub/app/db.py
  - hub/frontend/src/permissions.js
  - hub/frontend/src/pages/AdminConsolePage.jsx
  - hub/frontend/src/components/UsersSection.jsx
  - hub/frontend/src/components/AuditLogSection.jsx
  - hub/frontend/src/pages/ProfilePage.jsx
relates_to: [hub, data-model, dashboard-ui, credentials, pairing, scheduling, metrics, testing]
---

Real multi-user accounts with four roles, replacing an earlier single
shared admin password. Motivated by a real need: a school lab deployment
has more than one person who should be able to act on it, but not all of
them should have the run of the whole fleet.

**Roles** (`User.role`, checked throughout `auth.py`):

- `admin` — unrestricted view/edit of everything, including the user
  list and audit log.
- `group_manager` — view/edit restricted to node(s) in their own
  group(s) (`User.scope`, comma-separated group names). Can mint pairing
  tokens and pair discovered nodes into their own group only; can apply
  an existing credential fleet-wide within their group, not `apply-all`.
- `machine_manager` — view/edit restricted to specific node id(s)
  (`User.scope`). Can apply a credential to their own node(s) but can't
  mint pairing tokens or pair discovered nodes at all.
- `viewer` — read-only, but sees *everything* — the inverse of the other
  two: unrestricted visibility, zero write access.

group_manager/machine_manager get a **restricted view**, not just
restricted edits — nodes outside their scope are invisible, not just
uneditable (confirmed as the intended design, not an accident). Server-
side enforcement: `auth.py::can_access_node()`/`get_node_or_403()` for
single-node reads/writes, `nodes.py::scoped_nodes_query()` for list
endpoints (nodes/groups/metrics) — every list a scoped user sees is
already filtered server-side.

**Credentials/pairing/discovery stay narrower still**: creating/deleting
a credential and `apply-all` are admin-only regardless of role; minting
a pairing token or discovery-pairing is admin/group_manager, forced into
the caller's own group (`auth.py::require_group_access()`). See
[credentials](credentials.md)/[pairing](pairing.md).

**Auth core**: bcrypt password hashing, in-memory session cookie keyed
to a real `user_id`. `POST /api/login` takes `{username, password}`; the
response's `role` field drives the dashboard's nav without a second
round-trip. First boot with an empty `users` table seeds one
`username="admin"` row from `GRIDKEEPER_ADMIN_PASSWORD`
(`auth.py::bootstrap_admin_user()`) — keeps the existing Docker
quickstart working unchanged.

**Audit log**: `audit.py::record_audit()`, a synchronous DB write in the
same transaction as the action (after it succeeds, never before).
`AuditLogEntry` denormalizes `username` so an entry survives that user
being deleted. Admin-only `GET /api/audit-log`, capped at 500 rows.
Called from every state-changing endpoint, including all command
dispatch via `nodes.py::dispatch_command()` — the single choke point for
both direct commands and credential-apply commands.

**Frontend**: `App.jsx` tracks `role` and conditionally shows one
**Admin Console** nav item (Users + Audit Log sub-tabs, since both are
admin-only on the backend) and a **Profile** page (visible to everyone).
`permissions.js::getPermissions(role)` mirrors `auth.py`'s rules and is
threaded down through Fleet/Credentials so write controls (Start/Stop/
Attach/Detach, group/schedule edit, credential apply/delete/create) are
hidden — not just backend-blocked — for a role that can't use them; the
backend 403 is still the real enforcement boundary.

**Verified**: real-browser Playwright pass covering user CRUD through
the UI, role-based nav gating (Admin Console/Profile), a direct
`fetch('/api/users')` 403 for a non-admin session, and a seeded node
confirming every write control disappears for a `viewer` account while
status values still render, backed by a direct API 403.
`group_manager`/`machine_manager` scope isolation independently verified
live: each sees and can only write to their own scoped node(s),
confirmed via both the DOM and direct `/api/nodes` fetches. Deployed to
the production hub with the existing `GRIDKEEPER_ADMIN_PASSWORD` still
logging in as `admin`.
