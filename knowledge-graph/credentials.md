---
id: credentials
type: component
status: implemented-verified
files:
  - manager/app/crypto.py
  - manager/app/db.py
  - manager/app/api/credentials.py
  - manager/frontend/src/components/CredentialsSection.jsx
relates_to: [manager, boinc-backend, dashboard-ui, data-model]
---

A saved-BOINC-account-key repository, added 2026-08-19 in response to a
real usability question: for a school lab enrolling many machines under
one institutional BOINC account (see [[grid_manager_school_use_case]]),
pasting the same account key into every machine's attach form separately
doesn't scale. `CredentialKey` (`manager/app/db.py`) stores `name`,
`project_url`, and `encrypted_account_key`; `manager/app/crypto.py`
Fernet-encrypts the key at rest using a new `GRIDKEEPER_SECRET_KEY` env
var, deliberately separate from `GRIDKEEPER_ADMIN_PASSWORD` (auth.py) --
that one gates API access, this one protects data already sitting in
`grid.db`, and conflating the two would mean the admin password doubles
as an encryption key, which is a much bigger blast radius if it ever
needs rotating.

This is the *first* place the manager persists an account key at all --
every existing credential path (`boinc-backend.md`'s `attach_project`)
deliberately never stores the key, only redacting it from the `commands`
audit-log table before it's written (`workers.py::_redact_payload`). The
repository is an intentional, scoped exception to that "never persist"
rule, not a relaxation of it: the key is only ever decrypted in-memory,
at the moment `credentials.py::apply_credential` dispatches an
`attach_project` command, reusing the exact same dispatch path (and
therefore the exact same audit-log redaction) as a manually-typed key
would.

`workers.py::issue_command`'s body was refactored into a standalone
`dispatch_command(db, worker, backend, action, payload)` helper so both
the direct `/api/workers/{id}/commands` route and
`/api/credentials/{id}/apply` share one WebSocket-dispatch/timeout/audit
code path rather than duplicating it.

**API**: `POST /api/credentials` (create, key never echoed back in the
response), `GET /api/credentials` (list, metadata only), `DELETE
/api/credentials/{id}`, `POST /api/credentials/{id}/apply` (body
`{worker_id}` — single-worker only, see below). All admin-gated like
every other route.

**Verified live 2026-08-19**: created a real credential from the
Einstein@Home account key used to verify [[grid_manager_boinc_attach_verified]],
applied it to the actual enrolled worker through the real REST API (not
just the pytest suite), confirmed `attached: true`, confirmed the
`account_key` field came back `"***redacted***"` in the apply response
exactly like a direct attach, and confirmed `last_used_at` updated.
11 new tests in `manager/tests/test_credentials.py` cover create/list/
delete/apply, duplicate-name rejection, 404s, the offline-worker 409,
redaction, and the "no `GRIDKEEPER_SECRET_KEY` configured" 500 path.

**Deliberately out of scope for this pass**: fleet/group-wide apply
(`apply` only takes one `worker_id`) — the user explicitly asked for
single-worker apply first, group fan-out as an explicit follow-up, given
`Worker.group` (`data-model.md`) already exists and is the natural
target for it. Also out of scope: FAH credentials (`passkey`) — this
repository's shape (`project_url` + one key) matches BOINC's
`attach_project` specifically and wasn't generalized to FAH's rather
different `set_config` payload, since there was no concrete need for it
yet.
