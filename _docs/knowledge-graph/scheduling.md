---
id: scheduling
type: component
status: implemented-untested
files:
  - node/grid_node/schedule.py
  - hub/app/api/schedule.py
relates_to: [hub, node, boinc-backend, fah-backend, wire-protocol, data-model, dashboard-ui]
---

Hours/idle restrictions on when a node is allowed to run — the
"donate cycles when idle, not during classwork" requirement (see
`_docs/REQUIREMENTS.md` §1, school-lab primary use case). A
`SchedulePolicy` is set fleet-wide (`POST /api/schedule/apply-all`),
per-group (`POST /api/schedule/apply-group/{group}` — e.g. a library
open later than classrooms, see [pairing](pairing.md) for how machines
get grouped), or per-node (`PUT /api/nodes/{id}/schedule`), stored on
the `nodes` row, pushed as a `{"type": "schedule", ...}` frame (see
[wire-protocol](wire-protocol.md)) both immediately and again on every
reconnect.

**Enforcement deliberately differs by backend** — not a missed
abstraction, a design choice: BOINC already has a mature native
idle/hours engine, so `boinc-backend.py::apply_schedule()` just rewrites
`global_prefs_override.xml` once and lets BOINC's own daemon enforce it.
FAH has no equivalent, so `daemon.py::_fah_schedule_loop` polls the
policy every 60s and pauses/unpauses directly — and runs as an
independent background task, *not* nested in the WebSocket connection's
task group, specifically so a network drop doesn't also suspend schedule
enforcement.

Full design rationale: `_docs/REQUIREMENTS.md` §7.

**Partially verified**: the policy-setting/wire-delivery path (`PUT
/api/nodes/{id}/schedule` persists and pushes the `schedule` frame on
connect/reconnect) and the underlying commands each side calls
(`suspend_all`/`resume_all` for BOINC, `pause`/`unpause` for FAH) are all
confirmed against real installs — see
[boinc-backend](boinc-backend.md)/[fah-backend](fah-backend.md). Status
stays `implemented-untested` because the schedule-specific piece on top
of those calls hasn't been watched live: `apply_schedule()`'s
`global_prefs_override.xml` actually changing BOINC's Activity behavior,
and `_fah_schedule_loop` crossing a real hours/idle boundary on its own.
