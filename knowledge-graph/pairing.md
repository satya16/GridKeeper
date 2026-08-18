---
id: pairing
type: component
status: implemented-verified
files:
  - manager/app/api/pairing.py
  - manager/app/api/discovery.py
  - manager/app/discovery.py
  - manager/app/enrollment.py
  - worker/grid_worker/pairing.py
relates_to: [manager, worker, data-model, dashboard-ui]
---

Two independent enrollment paths, both ending at
`enrollment.py::create_worker()` (a `Worker` row + bearer token — see
[data-model](data-model.md)):

- **Manual/token** (`api/pairing.py`): admin mints a one-time token from
  the dashboard (`POST /api/pairing-tokens`); worker exchanges it via
  `POST /api/enroll`, run manually with `grid-worker enroll --manager
  ... --token ...`. Works over WAN, no LAN required. A token can carry a
  `group` (e.g. "Lab 1") that the worker created from it inherits
  automatically — the bulk-lab-enrollment path: mint one token per room,
  every machine paired with it lands in that group with no per-machine
  follow-up. Any worker's group can also be changed later regardless of
  how it enrolled, via `PUT /api/workers/{id}/group`. See
  [scheduling](scheduling.md) for the main reason groups matter
  (per-group schedule) and [data-model](data-model.md) for the schema.
- **LAN discovery + 6-digit code** (`api/discovery.py` +
  `manager/app/discovery.py` on the manager side, `worker/grid_worker/pairing.py`
  on the worker side): the expected common path. Worker advertises via
  mDNS (`_grid-worker._tcp.local.`) and runs a tiny local HTTP listener;
  manager browses mDNS continuously and, on `POST
  /api/discovery/{id}/pair`, dials the worker directly to verify the code
  and hand over credentials. Full handshake diagram in
  `docs/REQUIREMENTS.md` §6.

**Verified** (2026-08-11, local smoke test): both flows confirmed working
end to end, including the LAN flow's mDNS advertise → browse → discover →
direct-dial → verify → credential-handoff → "starts running with no
restart" sequence in full — this was the single most uncertain piece in
the whole project (untested third-party `zeroconf` on both ends) and it
worked on the first real attempt. One real bug found and fixed in the
process: `/pair-complete` wasn't sending the manager's *final* chosen
name (which can differ from the worker's self-reported one if the admin
typed an override during pairing) back to the worker, so the worker's
local config could permanently disagree with the dashboard on its own
name. Fixed by adding `name` to the `/pair-complete` payload.

Not yet tested: a second/different network's multicast behavior (this
test was worker and manager on the same host) — still worth confirming
across two genuinely separate machines on a real LAN before fully
trusting it in a school deployment.
