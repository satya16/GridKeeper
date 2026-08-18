---
id: scheduling
type: component
status: implemented-untested
files:
  - worker/grid_worker/schedule.py
  - manager/app/api/schedule.py
relates_to: [manager, worker, boinc-backend, fah-backend, wire-protocol, data-model, dashboard-ui]
---

Hours/idle restrictions on when a worker is allowed to run — the
"donate cycles when idle, not during classwork" requirement (see
`docs/REQUIREMENTS.md` §1, school-lab primary use case). A
`SchedulePolicy` is set fleet-wide (`POST /api/schedule/apply-all`),
per-group (`POST /api/schedule/apply-group/{group}` — e.g. a library
open later than classrooms, see [pairing](pairing.md) for how machines
get grouped), or per-worker (`PUT /api/workers/{id}/schedule`), stored on
the `workers` row, pushed as a `{"type": "schedule", ...}` frame (see
[wire-protocol](wire-protocol.md)) both immediately and again on every
reconnect.

**Enforcement deliberately differs by backend** — not a missed
abstraction, a design choice: BOINC already has a mature native
idle/hours engine, so `boinc-backend.py::apply_schedule()` just rewrites
`global_prefs_override.xml` once and lets BOINC's own daemon enforce it.
FAH has no equivalent, so `worker.py::_fah_schedule_loop` polls the
policy every 60s and pauses/unpauses directly — and runs as an
independent background task, *not* nested in the WebSocket connection's
task group, specifically so a network drop doesn't also suspend schedule
enforcement.

Full design rationale: `docs/REQUIREMENTS.md` §7. Unverified caveats
(BOINC prefs file format, `loginctl`-based idle detection): `CLAUDE.md`.

**Partially verified** (2026-08-11, local smoke test): the policy-setting
and wire-delivery path is confirmed — `PUT /api/workers/{id}/schedule`
persisted correctly and the worker received the `schedule` frame both on
initial connect and on reconnect. Status stays `implemented-untested`
because the test machine has neither BOINC nor FAH installed, so neither
enforcement path actually ran — `apply_schedule()`'s `boinccmd
--set_global_prefs_override` call and `_fah_schedule_loop`'s
pause/unpause calls remain unexercised. This is the next thing to verify,
ideally on a machine with a real BOINC and/or FAH install.
