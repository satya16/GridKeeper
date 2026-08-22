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

A saved-BOINC-account-key repository: for a school lab enrolling many
machines under one institutional BOINC account, pasting the same key
into every machine's attach form separately doesn't scale.
`CredentialKey` (`hub/app/db.py`) stores `name`, `project_url`, and
`encrypted_account_key`; `hub/app/crypto.py` Fernet-encrypts the key at
rest using `GRIDKEEPER_SECRET_KEY`, deliberately separate from the admin
auth system — that one gates API access, this one protects data already
sitting in `grid.db`.

The key is only ever decrypted in-memory, at the moment
`credentials.py::apply_credential` dispatches an `attach_project`
command through `nodes.py::dispatch_command` — the same shared dispatch
path (and therefore the same audit-log redaction, see
[boinc-backend](boinc-backend.md)) a manually-typed key would use.

**API**: `POST /api/credentials` (create), `GET /api/credentials` (list,
metadata only, no key material), `DELETE /api/credentials/{id}`, and
three apply variants — `POST .../apply` (single node), `.../apply-group/{group}`,
`.../apply-all` — mirroring `schedule.py`'s apply-group/apply-all
philosophy (an unknown/empty group matches no nodes rather than
erroring; an offline node in a batch is reported `skipped`, not a batch
failure). Create/delete/apply-all are admin-only; apply-group is
admin/group_manager (scoped to their own group); apply (single node) and
list are available to any role that can see that node — see
[users-and-roles](users-and-roles.md).

Out of scope: FAH credentials (`passkey`) — this repository's shape
matches BOINC's `attach_project` specifically, not FAH's `set_config`.

**Verified live**: created a real credential from a real Einstein@Home
account key, applied it to a real enrolled node through the actual REST
API (not just pytest), confirmed the key round-trips correctly to the
node while the audit-log/API response shows it redacted.
`hub/tests/test_credentials.py` covers create/list/delete/apply (single,
group, all), scope permissions, duplicate-name rejection, 404s, the
offline-node/no-secret-key error paths, and that an all-offline batch
doesn't decrypt the key or bump `last_used_at`.
