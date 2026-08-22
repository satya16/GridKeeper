---
id: data-model
type: data-model
status: implemented-verified
files:
  - hub/app/db.py
relates_to: [hub, pairing, scheduling, wire-protocol, credentials, users-and-roles]
---

SQLite via SQLAlchemy (`hub/app/db.py`), six tables:

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
  whichever node redeems the token), `used_at`/`used_by_node_id` to
  enforce single-use.
- **`commands`**: an audit log of every command issued to a node —
  backend, action, payload, status (`pending|sent|ok|error|timeout`),
  result. Written even for commands that time out or fail to send.
- **`credential_keys`**: saved BOINC account keys, encrypted at rest
  (`crypto.py`) — see [credentials](credentials.md).
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
migration once this has real deployed data.

**Verified**: killed and restarted a node process — reconnected using
only its saved config (no re-enroll), came back online, and its
previously-set `schedule_json` was re-sent immediately on reconnect,
exactly as designed. `commands` audit rows confirmed written correctly
including for an error result.
