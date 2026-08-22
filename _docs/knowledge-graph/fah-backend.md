---
id: fah-backend
type: component
status: implemented-verified
files:
  - node/grid_node/backends/fah.py
relates_to: [node, scheduling]
---

Controls a locally-running FAHClient by speaking JSON over its WebSocket
API at `ws://127.0.0.1:7396/api/websocket` (`websockets.sync.client`,
already a dependency via `daemon.py`'s hub connection). This is the
"Bastet" rewrite's actual protocol (`fah-client` 8.x) — an earlier
version of this backend targeted the old v7 raw-socket PyON protocol on
port 36330, which the current client doesn't speak at all; rewritten and
verified live against a real daemon.

`get_status()` returns `{"slots": [...], "account": {"user", "team",
"cause", "fold_anon"}}` (deliberately omitting `passkey`). Commands:
`pause_all`/`unpause_all` (plain `{"cmd": "pause"/"unpause"}` — the
richer `master`-branch protocol with per-group control isn't honored by
the currently-shipped client, confirmed live, so `pause_slot`/
`unpause_slot` accept a `slot_id` for API-shape compatibility but act
globally, same as `pause_all`/`unpause_all`), and `set_config` (`user`/
`team`/`passkey`/`fold_anon`/`cause`, confirmed *is* honored unlike the
"state" command). Unlike [boinc-backend](boinc-backend.md), FAH has no
native idle/hours scheduling — see [scheduling](scheduling.md) for why
the node enforces it directly instead.

Valid `cause` values fetched live from
`https://api.foldingathome.org/project/cause` (same endpoint the
official web-control frontend uses) and hardcoded into the dashboard as
`FAH_CAUSES` rather than fetched at runtime. `passkey` gets the same
hub-side redaction as BOINC's `account_key` (see
[boinc-backend](boinc-backend.md)).

**Verified live** against a real `fah-client` 8.x daemon: `is_available()`,
`get_status()`, `pause_all()`/`unpause_all()`/`set_config()` all
round-tripped through the real command-dispatch path and confirmed via
`config.paused`/delta pushes flipping correctly; `fold_anon: true`
genuinely got a real work unit assigned. Bugs found this way (mismatches
between the upstream `master` branch's protocol and what the
actually-shipped client speaks — see the "Bastet rewrite" note above) are
covered by `node/tests/test_fah.py` fixtures captured from live output.
