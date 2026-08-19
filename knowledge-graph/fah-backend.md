---
id: fah-backend
type: component
status: implemented-verified
files:
  - node/grid_node/backends/fah.py
relates_to: [node, scheduling]
---

Controls a locally-running FAHClient by speaking its local control socket
(127.0.0.1:36330) directly — a plain-text protocol whose responses are
PyON (Python literal syntax), parsed here via `ast.literal_eval` after
stripping the `PyON <ver> <name>` header and `---` footer. `get_status()`
combines `slot-info` and `queue-info` to build per-slot progress; commands
(`pause_all`, `unpause_all`, `pause_slot`, `unpause_slot`) are simple text
commands over the same socket.

Unlike [boinc-backend](boinc-backend.md), FAH has no native idle/hours
scheduling — that's why [scheduling](scheduling.md) has to poll and
pause/unpause from the node side for FAH specifically, rather than
delegating to FAH itself.

Framing/prompt-detection logic matches FAHClient's documented protocol
but has never been exercised against a live FAHClient — see the module
docstring and `CLAUDE.md`.

Not touched by the 2026-08-11 smoke test at all (no FAHClient in the test
environment, and unlike [boinc-backend](boinc-backend.md) no command was
issued against it to at least confirm the failure path) — still the
least-verified piece of the node.

**Protocol mismatch found 2026-08-18 (real-hardware install attempt):**
installed the only FAHClient currently distributed by foldingathome.org —
`fah-client` 8.1.18 (`.deb` from
`download.foldingathome.org/releases/public/fah-client/debian-stable-64bit/release/`,
built 2026-07-13), the "Bastet" rewrite
([FoldingAtHome/fah-client-bastet](https://github.com/FoldingAtHome/fah-client-bastet)
on GitHub). It runs fine (`fah-client.service` active, logs clean) but
**does not open the old v7 raw-socket PyON port 36330 at all** — confirmed
both by `ss -tln` (no 36330 listener; only `127.0.0.1:7396`) and by
reading `src/fah/client/Server.cpp` upstream, which registers exactly one
real API surface: `GET /api/websocket` (a JSON WebSocket, see
`WebsocketRemote.cpp` — `send()` takes a `cb::JSON::ValuePtr`), plus
`/ping` and a redirect to the web-control UI for everything else. Every
other path 404s (confirmed live against the running daemon).

This means `fah.py`'s core assumption — a plain-text PyON protocol on
port 36330 — isn't just unverified, it's **written against a protocol
version this client no longer speaks at all**.

**Rewritten and verified live 2026-08-18.** `fah.py` now speaks
JSON-over-WebSocket against `ws://127.0.0.1:7396/api/websocket`, using
`websockets.sync.client` (already a project dependency via `daemon.py`'s
own hub connection — no new dependency added). One important catch
found only by testing against the real daemon, not the source: **GitHub's
`FoldingAtHome/fah-client-bastet` `master` branch is ahead of what
foldingathome.org actually distributes.** `master` documents a richer
protocol — `{"cmd": "state", "state": ..., "group": ...}` plus a
top-level `"groups"` dict for per-resource-group control — but against a
real `fah-client` 8.1.18 daemon (the only version currently downloadable)
that message is silently accepted and does *nothing* (no error, no state
change, confirmed by diffing `config.paused` before/after and by watching
for — and not getting — a delta push). The wire format this version
*actually* sends never has a `"groups"` key at all; it's flat
`{"units": [...], "config": {...}, "info": {...}}`, and work units'
`"group"` field is always `""`. What *does* work, confirmed via the
resulting delta push (`["config", "paused", true]`): the plain
`{"cmd": "pause"}` / `{"cmd": "unpause"}` form — which `master`'s
`Remote.cpp` labels "Deprecated" in a comment, but is the only form this
shipped build honors. Consequence: **there is no per-slot/per-group
control in the currently-installed client** — `pause_slot`/`unpause_slot`
in `fah.py` accept a `slot_id` for API-shape compatibility with
`dashboard.js` but act globally, same as `pause_all`/`unpause_all`, since
there's nothing narrower to target.

Verified end-to-end against the real daemon on 2026-08-18: `is_available()`,
`get_status()` (correct empty-slots shape with no work unit assigned),
`pause_all()`/`unpause_all()` (round-tripped through `daemon.py`'s actual
`_execute_command` dispatch path, not just called directly — confirmed
`config.paused` flips both ways). 7 tests in `node/tests/test_fah.py`
rewritten to match and passing.

**`set_config()` added + real work-unit fields verified, same day, second
pass.** Tested whether the richer `master`-only commands extend to
`{"cmd": "config", "config": {...}}` too, expecting the same silent
no-op as `"cmd": "state"` above — it doesn't: confirmed live (delta
pushes like `["config", "cause", "cancer"]`, persisted across a fresh
connection) that `config` *is* honored on 8.1.18, unlike `state`. Added
`set_config(fields)` — whitelisted to `user`/`team`/`passkey`/
`fold_anon`/`cause` only — plus a `set_config` `ACTIONS` entry, and
extended `get_status()` to report `{"slots": [...], "account": {"user",
"team", "cause", "fold_anon"}}` (deliberately omitting `passkey`, which
would otherwise sit in the hub's per-node status table in
plaintext on every poll).

Setting `fold_anon: true` (cause `"any"`, no account) during this test
**actually got a real work unit assigned within about a second** — so
this genuinely starts real folding, not just a config write; had to
pause it again afterward rather than leave real compute running
unasked. That real work unit also caught a real bug: `get_status()`'s
project-number mapping was wrong. It read `unit["wu"]["project"]`
(guessed from the upstream C++ source, never checked live); the real
field is `unit["assignment"]["project"]` — `"wu"` actually holds
`run`/`clone`/`gen`/collection-server fields, no project number at all.
Fixed and now confirmed against real data (project `18292`). Another
concrete example, on top of the `state`-vs-`pause` mismatch above, of
why this client's wire format needs checking live rather than trusted
from source alone.

The valid `cause` values (`any`, `alzheimers`, `cancer`, `covid-19`,
`diabetes`, `huntingtons`, `influenza`, `parkinsons`) aren't from source
either — fetched live from `https://api.foldingathome.org/project/cause`,
the same endpoint the official `fah-web-client-bastet` frontend calls
(`src/CommonSettings.vue`'s cause `<select>`, backed by `src/api.js`'s
`get_causes()`). Hardcoded into `dashboard.js` as `FAH_CAUSES` rather
than fetched at runtime, to avoid giving the hub a new external
dependency for a list that changes rarely.

Like BOINC's `account_key` (see [boinc-backend](boinc-backend.md)), FAH's
`passkey` is a long-lived credential — `set_config`'s payload gets the
same hub-side redaction treatment
(`hub/app/api/nodes.py::_SENSITIVE_PAYLOAD_FIELDS`).

Dashboard: `renderFahBlock` in `dashboard.js` now shows current
account/cause state and a collapsed "Account & cause…" form (cause
dropdown, fold-anonymously checkbox, username/team/passkey fields — only
non-blank fields are actually sent, so an empty field never overwrites a
real value with blank/zero). See
[dashboard-ui](dashboard-ui.md).
