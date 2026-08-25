---
id: data-model
type: data-model
status: implemented-verified
files:
  - hub/app/db.py
relates_to: [hub, pairing, scheduling, wire-protocol, credentials, users-and-roles, plugin-registry]
---

SQLite via SQLAlchemy (`hub/app/db.py`), seven tables:

- **`nodes`** (`Node` model): id (UUID), name (unique), `token_hash`
  (bearer token, hashed — never stored plaintext), `os_name`, `backends`
  (comma-separated string, not a join table — fine at this scale),
  `group` (free-text room/lab label, `""` = ungrouped — not a separate
  table since groups have no attributes of their own, just a name nodes
  can share; see [pairing](pairing.md)/[scheduling](scheduling.md) for how
  it's set and used), `last_seen_at`, `last_status_json` (the most recent
  status frame, denormalized so the dashboard has data even for offline
  nodes), `schedule_json` (current [scheduling](scheduling.md) policy,
  `null` = unrestricted).
- **`pairing_tokens`**: one-time tokens for the manual
  [pairing](pairing.md) flow — token, label, `group` (inherited by
  whichever node redeems the token), `schedule_json` (optional — seeded
  onto the node the moment it's created from this token, see
  [pairing](pairing.md)'s default-schedule note), `used_at`/
  `used_by_node_id` to enforce single-use.
- **`commands`**: an audit log of every command issued to a node —
  backend, action, payload, status (`pending|sent|ok|error|timeout`),
  result. Written even for commands that time out or fail to send.
- **`credential_keys`**: saved backend credentials (e.g. a BOINC project
  account key), encrypted at rest (`crypto.py`) — `backend` +
  `static_fields_json` (non-secret fields like `project_url`) +
  `encrypted_secret`, generalized from a BOINC-only shape via
  [plugin-registry](plugin-registry.md) — see [credentials](credentials.md).
- **`backend_capabilities`**: the hub's registry of every backend it's
  ever seen a node report (label, which action/payload fields are
  sensitive, saved-credential shape if any, action list) — populated from
  each node's status frame, not hardcoded; see
  [plugin-registry](plugin-registry.md).
- **`users`**: real per-user accounts (`username`, bcrypt
  `password_hash`, `role`, comma-separated `scope`) — see
  [users-and-roles](users-and-roles.md).
- **`audit_log`**: durable "who did what" records, `username` denormalized
  so an entry still reads correctly after that user is deleted — see
  [users-and-roles](users-and-roles.md).

Everything here persists permanently — a node paired once, and whatever
schedule was set for it, survives hub restarts and node reconnects.
No migrations tooling; `Base.metadata.create_all()` only ever adds
missing tables, so a schema change to an *existing* table needs a manual
migration once this has real deployed data. `credential_keys`' BOINC-only
-> backend-agnostic generalization needed exactly this: `db.py::init_db()`
runs a small hand-written, idempotent migration (`_migrate_credential_keys`/
`_migrate_pairing_tokens`) that adds the new columns and backfills them
from the old ones where present, without ever dropping the old columns
(SQLite `DROP COLUMN` support varies by version) — covered by
`hub/tests/test_db_migration.py` against a throwaway old-schema SQLite
file, not the shared test-session engine (whose schema is already current
by the time any test runs).

**Verified**: killed and restarted a node process — reconnected using
only its saved config (no re-enroll), came back online, and its
previously-set `schedule_json` was re-sent immediately on reconnect,
exactly as designed. `commands` audit rows confirmed written correctly
including for an error result. `backend_capabilities` confirmed populated
live from a real node's status frame (`GET /api/backends` reflecting real
BOINC/FAH/GIMPS data, see [plugin-registry](plugin-registry.md)).
