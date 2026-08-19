# Testing

Two layers: automated tests (no hardware needed, run them constantly)
and a manual checklist (needs real BOINC/FAH installs, a browser, and/or
a second machine — run these before trusting a release).

## Automated tests

```bash
cd hub && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest tests/ -v
cd node  && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest tests/ -v
```

(If you haven't created the venvs yet, see the top-level README's
Quickstart first.)

**`hub/tests/`** — FastAPI `TestClient` against a real (temp-file)
SQLite DB, with the mDNS discovery registry stubbed out (no real
network) and the WebSocket connection hub monkeypatched per-test to
simulate an online/responding node. Covers: the HTTP Basic auth gate,
both enrollment paths (including the "duplicate name doesn't burn the
pairing token" edge case), node listing/lookup, command dispatch
(offline-node 409, unknown-node 404, success and node-side-error
result shapes), and schedule policy persistence (per-node and
fleet-wide).

**`node/tests/`** — pure unit tests against the backend/scheduling
logic with all I/O (`subprocess`, sockets, `datetime.now()`,
`websockets.sync.client`) monkeypatched. Covers: `boinccmd` text-output
parsing (`--get_simple_gui_info`/`--get_cc_status`), `apply_schedule()`'s
generated `global_prefs_override.xml` content, FAHClient's JSON/WebSocket
message shapes (`get_status()`'s unit-to-slot mapping, both dict- and
list-shaped `units`, the exact `pause`/`unpause` commands sent), the
local status page's HTML rendering (`node-local-ui`, including a real
`ThreadingHTTPServer` round-trip and an XSS-escaping check), and — the
subtlest logic in the whole project —
`schedule.py::_within_active_hours()`'s midnight-wrap arithmetic and
`should_run()`'s fail-open behavior when idle detection is unavailable.

**What these tests deliberately don't cover** (see "Manual checklist"):
actually shelling out to a real `boinccmd`, real mDNS traffic, or
anything rendered in a browser (the local status page's HTML is tested
over real HTTP, just never painted by an actual browser). A real
FAHClient *was* exercised manually, not mocked — see "Real
Folding@home" below, and note it turned up a real protocol-version
mismatch that mocks alone never would have caught. Mocking these
wouldn't test anything meaningful — the risk is entirely in "does the
real thing behave like the docs say it does," which only the real thing
can answer.

## Manual checklist

Everything below has a **last verified** date. If it's stale, don't
trust it — re-run it. See `CLAUDE.md` and `_docs/knowledge-graph/` for the
detailed, dated per-component verification notes this summarizes.

### Core system + LAN pairing — last verified 2026-08-11 ✅

Node and hub as separate processes on one machine, no BOINC/FAH
installed:

1. Boot the hub, confirm `/` (with auth) and `/api/nodes` respond.
2. Manual token flow: mint a token, `grid-node enroll --hub ...
   --token ...`, `grid-node run`, confirm it shows online.
3. Issue a command via `POST /api/nodes/{id}/commands`, confirm the
   result round-trips (expect a graceful "not found" error with no
   BOINC/FAH installed — that's the point, confirms error handling).
4. Kill and restart the node with no re-enrollment; confirm it
   reconnects and any previously-set schedule policy is re-sent.
5. LAN flow: delete the node's config, `grid-node run` fresh,
   confirm a pairing code prints and the hub's `/api/discovery`
   picks it up, `POST /api/discovery/{id}/pair` with the code, confirm
   the node starts running with no restart and its local config
   matches whatever name the hub decided on.

### Real Folding@home — last verified 2026-08-18 ✅ (mostly)

Installed the real `fah-client` 8.1.18 daemon (the only version
foldingathome.org currently distributes) on real hardware and confirmed,
against the live daemon: `is_available()`, `get_status()` (correct empty
shape with no work unit assigned), `pause_all()`/`unpause_all()` — the
last two round-tripped through the actual `daemon.py` command-dispatch
path (`_execute_command`), not called directly, and confirmed via
`config.paused` flipping both ways. Along the way, found that the
protocol this backend originally targeted (v7 PyON) doesn't exist in the
shipped client at all — rewrote `fah.py` for the JSON/WebSocket API,
including a live-only discovery that even the upstream GitHub source is
ahead of the shipped binary (details: `_docs/knowledge-graph/fah-backend.md`).
Still open: `pause_slot`/`unpause_slot` couldn't be tested as
per-group actions since the shipped client has no group/slot concept at
all (they now act globally, correctly matching that reality, but there's
nothing narrower to verify against); the per-work-unit `project`/`progress`
field mapping was coded defensively from source but never checked
against a real actively-folding work unit (no FAH account linked on the
test machine, so it never received real work); `_fah_schedule_loop`
actually pausing/resuming FAH on an hours/idle boundary specifically
(the underlying `pause_all`/`unpause_all` calls it uses are now verified,
but the loop itself — reacting to a real schedule boundary — hasn't been
watched live).

### Real BOINC — last verified 2026-08-18 ✅ (mostly)

Attempted 2026-08-13, blocked, re-confirmed broken twice more on
2026-08-18 (fresh daemon start, then a full restart — same `EINTR`-on-
`recvfrom()`-then-never-retry hang traced via `strace` both times).
**Resolved same day, later on**: swapped Ubuntu's stale `boinc-client`
package (`8.2.9+dfsg-1build1`, universe repo) for BOINC's own official
pre-built release — `client_release/8.2/8.2.15` from
[github.com/BOINC/boinc/releases](https://github.com/BOINC/boinc/releases),
built specifically for this Ubuntu codename (`resolute`). `sudo dpkg -i`
over the existing package (same package name, clean replace, own
self-consistent systemd unit). The hang genuinely does not reproduce in
8.2.15 — confirmed via many repeated `boinccmd --get_cc_status` calls,
independently in a real user terminal (not just this project's
automation) and this project's usual tooling. `suspend_all()`/
`resume_all()` confirmed to actually change daemon state, round-tripped
through the real `daemon.py` dispatch path. Along the way, found and
fixed a real parsing bug this unblocked testing: `get_status()`'s
`run_mode` was reading a `"task mode:"` line that doesn't exist in this
client's `--get_cc_status` output at all (real field is `"current mode:"`
under a `"CPU status"` section) — was silently always `"unknown"`,
untested because the daemon-hang bug made this code path unreachable
until now. Full story: `_docs/knowledge-graph/boinc-backend.md`. Still open:
`attach_project`/`detach_project` against a real project (this machine
has no BOINC project account), and by extension the `Projects`/`Tasks`
block-parsing in `get_status()` against real non-empty data — those
field names (`"hub URL"`, `"suspended via GUI"`, etc.) are still
exactly as originally written from documentation/memory, never checked
live. `apply_schedule()`'s real effect on BOINC's Activity behavior is
also still unverified.

### Still open — needs real hardware/environment

- [ ] **BOINC project attach/detach + non-empty status parsing** — see
      above; needs a real BOINC project account, which this machine
      doesn't have.
- [ ] **Node local status page in a real browser** (added 2026-08-18,
      see `_docs/knowledge-graph/node-local-ui.md`): confirmed over real HTTP
      with real backend/metrics data from a real machine, but never
      actually painted by a browser. (The *hub* dashboard's
      equivalent gap is resolved — see `_docs/knowledge-graph/dashboard-ui.md`;
      this one's different code, stdlib Python `http.server`, not React,
      and hasn't had the same Playwright pass yet.)
- [ ] **LAN pairing across two separate machines** (this project's test
      so far had node and hub as two processes on one host, so
      mDNS multicast never had to cross a real network segment/router).
- [ ] **The `dataviz` palette validator** (`node
      scripts/validate_palette.js` from the skill's directory) — `node`
      turned out to be available via `nvm` after all (found 2026-08-18,
      just not always on `PATH`); this script specifically still hasn't
      actually been run, just newly unblocked.
