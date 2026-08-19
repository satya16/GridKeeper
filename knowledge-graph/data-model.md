---
id: data-model
type: data-model
status: implemented-verified
files:
  - manager/app/db.py
relates_to: [manager, pairing, scheduling, wire-protocol, credentials]
---

SQLite via SQLAlchemy (`manager/app/db.py`), three tables:

- **`workers`** (`Worker` model): id (UUID), name (unique), `token_hash`
  (bearer token, hashed — never stored plaintext), `os_name`, `backends`
  (comma-separated string, not a join table — fine at this scale),
  `group` (free-text room/lab label, `""` = ungrouped — not a separate
  table since groups have no attributes of their own, just a name workers
  can share; see [pairing](pairing.md)/[scheduling](scheduling.md) for how
  it's set and used), `last_seen_at`, `last_status_json` (the most recent
  status frame, denormalized so the dashboard has data even for offline
  workers), `schedule_json` (current [scheduling](scheduling.md) policy,
  `null` = unrestricted).
- **`pairing_tokens`**: one-time tokens for the manual
  [pairing](pairing.md) flow — token, label, `group` (inherited by
  whichever worker redeems the token), `used_at`/`used_by_worker_id` to
  enforce single-use.
- **`commands`**: an audit log of every command issued to a worker —
  backend, action, payload, status (`pending|sent|ok|error|timeout`),
  result. Written even for commands that time out or fail to send.

Everything here persists permanently — a worker paired once, and whatever
schedule was set for it, survives manager restarts and worker reconnects.
No migrations tooling; `Base.metadata.create_all()` only ever adds
missing tables, so a schema change to an *existing* table needs a manual
migration once this has real deployed data.

**Verified** (2026-08-11, local smoke test): killed and restarted a
worker process — reconnected using only its saved config (no re-enroll),
came back online, and its previously-set `schedule_json` was re-sent
immediately on reconnect, exactly as designed. `commands` audit rows
confirmed written correctly including for an error result.
