---
id: credentials
type: component
status: implemented-verified
files:
  - hub/app/crypto.py
  - hub/app/db.py
  - hub/app/api/credentials.py
  - hub/frontend/src/components/CredentialsSection.jsx
relates_to: [hub, boinc-backend, dashboard-ui, data-model, users-and-roles]
---

A saved-BOINC-account-key repository, added 2026-08-19 in response to a
real usability question: for a school lab enrolling many machines under
one institutional BOINC account (see [[grid_hub_school_use_case]]),
pasting the same account key into every machine's attach form separately
doesn't scale. `CredentialKey` (`hub/app/db.py`) stores `name`,
`project_url`, and `encrypted_account_key`; `hub/app/crypto.py`
Fernet-encrypts the key at rest using a new `GRIDKEEPER_SECRET_KEY` env
var, deliberately separate from `GRIDKEEPER_ADMIN_PASSWORD` (auth.py) --
that one gates API access, this one protects data already sitting in
`grid.db`, and conflating the two would mean the admin password doubles
as an encryption key, which is a much bigger blast radius if it ever
needs rotating.

This is the *first* place the hub persists an account key at all --
every existing credential path (`boinc-backend.md`'s `attach_project`)
deliberately never stores the key, only redacting it from the `commands`
audit-log table before it's written (`nodes.py::_redact_payload`). The
repository is an intentional, scoped exception to that "never persist"
rule, not a relaxation of it: the key is only ever decrypted in-memory,
at the moment `credentials.py::apply_credential` dispatches an
`attach_project` command, reusing the exact same dispatch path (and
therefore the exact same audit-log redaction) as a manually-typed key
would.

`nodes.py::issue_command`'s body was refactored into a standalone
`dispatch_command(db, node, backend, action, payload)` helper so both
the direct `/api/nodes/{id}/commands` route and
`/api/credentials/{id}/apply` share one WebSocket-dispatch/timeout/audit
code path rather than duplicating it.

**API**: `POST /api/credentials` (create, key never echoed back in the
response), `GET /api/credentials` (list, metadata only), `DELETE
/api/credentials/{id}`, `POST /api/credentials/{id}/apply` (body
`{node_id}` — single-node only, see below). All admin-gated like
every other route.

**Verified live 2026-08-19**: created a real credential from the
Einstein@Home account key used to verify [[grid_hub_boinc_attach_verified]],
applied it to the actual enrolled node through the real REST API (not
just the pytest suite), confirmed `attached: true`, confirmed the
`account_key` field came back `"***redacted***"` in the apply response
exactly like a direct attach, and confirmed `last_used_at` updated.
11 new tests in `hub/tests/test_credentials.py` cover create/list/
delete/apply, duplicate-name rejection, 404s, the offline-node 409,
redaction, and the "no `GRIDKEEPER_SECRET_KEY` configured" 500 path.

Also out of scope: FAH credentials (`passkey`) — this repository's shape
(`project_url` + one key) matches BOINC's `attach_project` specifically
and wasn't generalized to FAH's rather different `set_config` payload,
since there was no concrete need for it yet.

## Added 2026-08-19 (same day, second pass): group/fleet-wide apply

`POST /api/credentials/{id}/apply-group/{group}` and
`POST /api/credentials/{id}/apply-all`, mirroring `schedule.py`'s
`apply-group`/`apply-all` naming and "unknown/empty group matches no
nodes rather than erroring" philosophy. One real difference from the
schedule case: a schedule policy is *persisted state* pushed to a node
the next time it connects, so an offline node still "gets" it
eventually; `attach_project` is a one-shot command with nothing to
persist for later, so an offline node in the batch is reported as
`{"online": false, "status": "skipped"}` rather than erroring out the
whole batch or silently pretending it succeeded (`_apply_to_nodes()`
in `credentials.py`). The single-node `/apply` endpoint deliberately
keeps its original strict 404/409 behavior rather than being unified
with this tolerant one — picking one specific machine is a different
intent than fanning out across a mixed-availability fleet.

Dashboard: each saved credential's row now has one target picker (single
machine / whole group / all machines) instead of a bare node dropdown,
backed by `hub/frontend/src/api.js`'s `applyCredentialToGroup`/
`applyCredentialToAll`.

**Verified live** against the real enrolled node (grouped as "My
Laptop Lab"): `apply-group` on that group attached successfully
(`status: "ok"`), `apply-group` on a nonexistent group correctly
returned `[]`, and a follow-up `apply-all` call — since the project was
already attached from the prior call — correctly surfaced BOINC's real
`"Already attached to project"` error through the per-node result
(`status: "error"`) rather than crashing the batch. 8 new tests in
`hub/tests/test_credentials.py` cover group fan-out with a mixed
online/offline group, group scoping (a node in a different group isn't
touched), unknown group/credential, apply-all, and that an all-offline
batch doesn't decrypt the key or bump `last_used_at` for a no-op.
