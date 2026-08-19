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
  - hub/frontend/src/pages/UsersPage.jsx
  - hub/frontend/src/pages/AuditLogPage.jsx
  - hub/frontend/src/pages/ProfilePage.jsx
relates_to: [hub, data-model, dashboard-ui, credentials, pairing, scheduling, metrics, testing]
---

Real multi-user accounts with four roles, added 2026-08-19, replacing
[hub](hub.md)'s original single-shared-admin-password model (that
model's own note said as much: "nothing here is meant to survive contact
with a multi-user future"). Motivated by a real need: a school lab
deployment has more than one person who should be able to act on it, but
not all of them should have the run of the whole fleet.

**Roles** (`User.role` in `db.py`, checked throughout `auth.py`):

- `admin` — unrestricted view and edit of everything, including the user
  list itself and the audit log. Only an admin can create/edit/delete
  other users.
- `group_manager` — view and edit restricted to node(s) in their own
  group(s) (`User.scope`, comma-separated group names — same lightweight
  convention as `Node.backends`). Can also mint pairing tokens and pair
  discovered nodes, but only into their own group; can apply an existing
  credential fleet-wide *within* their group (`apply-group`), not
  `apply-all`.
- `machine_manager` — view and edit restricted to one or more specific
  node ids (`User.scope`, comma-separated node ids). Can apply an
  existing credential to their own node(s) but can't mint pairing tokens
  or pair discovered nodes at all (nothing new to enroll into).
- `viewer` — read-only, but sees *everything* (no scope restriction) —
  the one role that's the inverse of the other two: unrestricted
  visibility, zero write access.

This was a deliberate design choice confirmed with the user rather than
assumed: group_manager/machine_manager get a **restricted view**, not
just restricted edits — they don't see nodes outside their scope at all,
unlike viewer which sees everything read-only. Enforcement lives in two
places: `auth.py::can_access_node()`/`get_node_or_403()` for
single-node reads/writes, and `nodes.py::scoped_nodes_query()` for list
endpoints (`/api/nodes`, `/api/groups`, and `/api/metrics` via
`metrics.py` reusing the same helper) — every list a scoped user sees is
already filtered server-side, so the frontend needs zero client-side
scope logic of its own.

**Credentials/pairing/discovery stay admin-managed** as a deliberate
narrower carve-out: creating/deleting a saved credential, and minting a
fleet-wide `apply-all`, are admin-only regardless of role; a
group_manager can *apply* an existing credential or *mint a pairing
token* only within their own group (`auth.py::require_group_access()`);
a machine_manager can apply a credential to their own machine but has no
group-wide action at all. See [credentials](credentials.md) and
[pairing](pairing.md) for the endpoint-level detail.

**Auth core**: `bcrypt` password hashing (`auth.py::hash_password`/
`verify_password`), same in-memory session-cookie model as before but
now keyed to a real `user_id` (`_sessions: token -> {user_id,
expires_at}`) so `require_session` resolves *which* user, not just
"someone logged in." `POST /api/login` takes `{username, password}`
(was password-only); the response's `role` field lets the dashboard
decide which nav items to show without a second round-trip.

**Bootstrapping**: on first boot with an empty `users` table,
`auth.py::bootstrap_admin_user()` seeds one `username="admin"` row from
`GRIDKEEPER_ADMIN_PASSWORD` — keeps the existing `docker run -e
GRIDKEEPER_ADMIN_PASSWORD=...` quickstart working unchanged; that env
var is now "the first admin's password," not "the only password."

**Audit log**: `audit.py::record_audit()`, a plain synchronous DB write
in the same transaction as the action it's logging (called *after* the
action succeeds, never before) — `AuditLogEntry` rows with a
denormalized `username` (survives the user being deleted later),
`action`, `target`, and a free-form `detail_json`. Admin-only `GET
/api/audit-log`, capped at the most recent 500 rows, no pagination UI
yet. Every state-changing endpoint across the app calls it: user
CRUD, own-password change, node group/schedule changes, every command
dispatch (`nodes.py::dispatch_command()` is the single choke point for
*all* commands — both direct dashboard commands and credential-apply
commands route through it, so it's the one place that logs both
uniformly), credential create/delete, pairing token minting, and
discovered-node pairing.

**Frontend**: `LoginForm.jsx` gained a username field. `App.jsx` tracks
`role` (from `/api/session`'s response) alongside `authenticated`, and
conditionally shows **Users**/**Audit Log** nav items for admins only; a
**Profile** page (own username/role/scope + change-password form) is
visible to everyone. `UsersPage.jsx` is a table + inline create form +
edit modal, with a `Select` that switches between a group-tags picker
(group_manager) and a node multi-select (machine_manager) depending on
the chosen role — still round-trips through the same flat comma-separated
`scope` string the backend expects.

**Verified** (2026-08-19, real browser via Playwright against a local
test instance): admin login shows all six nav items including Users/
Audit Log/Profile; created a `group_manager` user with scope "Lab 1"
through the real UI form, confirmed it appears in the users table and in
the audit log with the correct `detail`; edited that user's role via the
modal and confirmed the table updated; deleted the user and confirmed
removal; logged in as that group_manager and confirmed Users/Audit Log
are absent from their nav (Profile still present), and confirmed a
direct `fetch('/api/users')` from their session gets a real 403, not
just a hidden button. Also caught and fixed one real bug this way: the
Users page's table didn't have `scroll={{ x: true }}`, so it overflowed
horizontally at 375px — same class of bug as earlier dashboard-ui mobile
fixes, same fix. All 93 backend pytest cases pass, including new
scope-filtering coverage across `test_nodes.py`, `test_credentials.py`,
`test_pairing.py`, `test_schedule.py`, and a new `test_users.py`.
Redeployed to the real running `satya16dev/grid-hub` container
(preserving its `gridkeeper-data` volume) and confirmed `admin`/the
existing `GRIDKEEPER_ADMIN_PASSWORD` logs in there too, with the
already-connected real node unaffected by the restart.
