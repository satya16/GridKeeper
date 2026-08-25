---
id: credentials
type: component
status: implemented-verified
files:
  - hub/app/crypto.py
  - hub/app/db.py
  - hub/app/api/credentials.py
  - hub/frontend/src/components/CredentialsSection.jsx
relates_to: [hub, boinc-backend, dashboard-ui, data-model, users-and-roles, plugin-registry]
---

A saved-credential repository: for a school lab enrolling many machines
under one institutional account, pasting the same key into every
machine's attach form separately doesn't scale. Originally BOINC-only
(`project_url` + `account_key`), generalized via
[plugin-registry](plugin-registry.md) so any backend that declares a
`CREDENTIAL_ACTION` (see `node/grid_node/backends/base.py`) works the same
way — `CredentialKey` (`hub/app/db.py`) now stores `backend`,
`static_fields_json` (non-secret fields the credential's action needs,
e.g. BOINC's `project_url`), and `encrypted_secret` (Fernet-encrypted at
rest via `hub/app/crypto.py`, using `GRIDKEEPER_SECRET_KEY` — deliberately
separate from the admin auth system, which gates API access rather than
protecting data already sitting in `grid.db`). FAH still has no
`CREDENTIAL_ACTION` (its passkey is tied to a specific user/team, not
shaped like a reusable project account key) — same boundary as before,
now structural rather than hardcoded.

`credentials.py::_credential_action_for()` looks up a backend's declared
shape from the `BackendCapability` registry (also
[plugin-registry](plugin-registry.md)) — a backend the hub has never seen
a node report yet (no capability row) can't have a credential created for
it (400), same practical effect as the old hardcoded restriction to
`"boinc"` but sourced from the wire instead of source code. Creating a
credential validates `static_fields` against the backend's declared set
exactly.

The secret is only ever decrypted in-memory, at the moment
`credentials.py::apply_credential`/`_apply_to_nodes` dispatches the
backend's declared action (`{**static_fields, key_field: secret}`) through
`nodes.py::dispatch_command`/`dispatch_command_to_nodes` — the same shared
dispatch path (and therefore the same audit-log redaction, sourced from
the same registry) a manually-typed key would use.

**API**: `POST /api/credentials` (create), `GET /api/credentials` (list,
metadata only, no secret material), `DELETE /api/credentials/{id}`, and
three apply variants — `POST .../apply` (single node), `.../apply-group/{group}`,
`.../apply-all` — mirroring `schedule.py`'s apply-group/apply-all
philosophy (an unknown/empty group matches no nodes rather than
erroring; an offline node in a batch is reported `skipped`, not a batch
failure; the apply-group/apply-all fan-out itself now reuses
`nodes.py::dispatch_command_to_nodes`, shared with the group/all *command*
endpoints — see [hub](hub.md)). Create/delete/apply-all are admin-only;
apply-group is admin/group_manager (scoped to their own group); apply
(single node) and list are available to any role that can see that node —
see [users-and-roles](users-and-roles.md).

**Verified live**: created a real credential from a real Einstein@Home
account key, applied it to a real enrolled node through the actual REST
API (not just pytest), confirmed the key round-trips correctly to the
node while the audit-log/API response shows it redacted — re-confirmed
2026-08-24 after the backend-agnostic generalization, same live node/key,
same round-trip. `hub/tests/test_credentials.py` covers create/list/delete/apply
(single, group, all), scope permissions, duplicate-name rejection, 404s,
the offline-node/no-secret-key error paths, unknown-backend/no-
credential-action/wrong-static-fields rejection, and that an all-offline
batch doesn't decrypt the secret or bump `last_used_at`.
