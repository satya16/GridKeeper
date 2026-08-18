# Testing

Two layers: automated tests (no hardware needed, run them constantly)
and a manual checklist (needs real BOINC/FAH installs, a browser, and/or
a second machine — run these before trusting a release).

## Automated tests

```bash
cd manager && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest tests/ -v
cd worker  && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest tests/ -v
```

(If you haven't created the venvs yet, see the top-level README's
Quickstart first.)

**`manager/tests/`** — FastAPI `TestClient` against a real (temp-file)
SQLite DB, with the mDNS discovery registry stubbed out (no real
network) and the WebSocket connection manager monkeypatched per-test to
simulate an online/responding worker. Covers: the HTTP Basic auth gate,
both enrollment paths (including the "duplicate name doesn't burn the
pairing token" edge case), worker listing/lookup, command dispatch
(offline-worker 409, unknown-worker 404, success and worker-side-error
result shapes), and schedule policy persistence (per-worker and
fleet-wide).

**`worker/tests/`** — pure unit tests against the backend/scheduling
logic with all I/O (`subprocess`, sockets, `datetime.now()`,
`websockets.sync.client`) monkeypatched. Covers: `boinccmd` text-output
parsing (`--get_simple_gui_info`/`--get_cc_status`), `apply_schedule()`'s
generated `global_prefs_override.xml` content, FAHClient's JSON/WebSocket
message shapes (`get_status()`'s unit-to-slot mapping, both dict- and
list-shaped `units`, the exact `pause`/`unpause` commands sent), the
local status page's HTML rendering (`worker-local-ui`, including a real
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
trust it — re-run it. See `CLAUDE.md` and `knowledge-graph/` for the
detailed, dated per-component verification notes this summarizes.

### Core system + LAN pairing — last verified 2026-08-11 ✅

Worker and manager as separate processes on one machine, no BOINC/FAH
installed:

1. Boot the manager, confirm `/` (with auth) and `/api/workers` respond.
2. Manual token flow: mint a token, `grid-worker enroll --manager ...
   --token ...`, `grid-worker run`, confirm it shows online.
3. Issue a command via `POST /api/workers/{id}/commands`, confirm the
   result round-trips (expect a graceful "not found" error with no
   BOINC/FAH installed — that's the point, confirms error handling).
4. Kill and restart the worker with no re-enrollment; confirm it
   reconnects and any previously-set schedule policy is re-sent.
5. LAN flow: delete the worker's config, `grid-worker run` fresh,
   confirm a pairing code prints and the manager's `/api/discovery`
   picks it up, `POST /api/discovery/{id}/pair` with the code, confirm
   the worker starts running with no restart and its local config
   matches whatever name the manager decided on.

### Real Folding@home — last verified 2026-08-18 ✅ (mostly)

Installed the real `fah-client` 8.1.18 daemon (the only version
foldingathome.org currently distributes) on real hardware and confirmed,
against the live daemon: `is_available()`, `get_status()` (correct empty
shape with no work unit assigned), `pause_all()`/`unpause_all()` — the
last two round-tripped through the actual `worker.py` command-dispatch
path (`_execute_command`), not called directly, and confirmed via
`config.paused` flipping both ways. Along the way, found that the
protocol this backend originally targeted (v7 PyON) doesn't exist in the
shipped client at all — rewrote `fah.py` for the JSON/WebSocket API,
including a live-only discovery that even the upstream GitHub source is
ahead of the shipped binary (details: `knowledge-graph/fah-backend.md`).
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

### Still open — needs real hardware/environment

- [ ] **Real BOINC** — attempted 2026-08-13, blocked, **re-confirmed
      twice more on 2026-08-18** (fresh `systemctl enable --now
      boinc-client`, then again after a full `systemctl restart` later
      the same day — same hang both times, new daemon PID each time). The
      second re-check added an `strace` narrowing: `boinccmd` sends a
      correct request and gets `EINTR` on `recvfrom()` almost
      immediately, then makes no further syscalls at all until killed --
      may implicate `boinccmd`'s own retry logic, not only the daemon.
      Full trace: `knowledge-graph/boinc-backend.md`. Ubuntu's
      `boinc-client` package (`8.2.9+dfsg-1build1`) has a reproducible,
      inconsistent GUI RPC daemon bug on real (non-VM) hardware, confirmed
      across a clean purge+reinstall with AppArmor ruled out. The `snap`
      alternative doesn't ship `boinccmd`. No newer package version exists
      in Ubuntu's archive to upgrade into (`apt-cache madison` checked
      2026-08-18). Full details, including the three unblock options if
      picked up again: `knowledge-graph/boinc-backend.md`. Once a working
      `boinccmd` is available somewhere: confirm `get_status()` parses
      real `boinccmd --get_simple_gui_info`/`--get_cc_status` output
      (compare field-by-field against `boinccmd`'s raw output, since this
      parser was written from documentation/memory, not a live sample —
      see `worker/grid_worker/backends/boinc.py`'s module docstring), and
      that `suspend_project`/`resume_project`/`suspend_all`/`resume_all`
      actually change BOINC's state. Then set a schedule policy with
      `only_when_idle` and/or `restrict_hours` and confirm
      `apply_schedule()`'s `global_prefs_override.xml` actually changes
      BOINC Manager's Activity behavior.
- [ ] **Dashboard in a real browser**: load `/`, confirm the worker
      cards, discovery panel, and fleet-schedule form render and their
      buttons/forms actually work (not just that the HTML skeleton is
      correct, which is all `TestClient` can confirm). Specifically the
      "Live metrics" charts per the `dataviz` skill's own "render it and
      look at it" step — label collisions, tooltip behavior, the device
      filter's 8-series cap, dark-mode contrast.
- [ ] **Worker local status page in a real browser** (added 2026-08-18,
      see `knowledge-graph/worker-local-ui.md`): confirmed over real HTTP
      with real backend/metrics data from a real machine, but never
      actually painted by a browser — same "no display in this sandbox"
      gap as the dashboard above.
- [ ] **LAN pairing across two separate machines** (this project's test
      so far had worker and manager as two processes on one host, so
      mDNS multicast never had to cross a real network segment/router).
- [ ] **The `dataviz` palette validator** (`node
      scripts/validate_palette.js` from the skill's directory) — still
      blocked on no `node` in every environment this has been worked on
      so far.
