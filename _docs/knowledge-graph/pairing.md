---
id: pairing
type: component
status: implemented-verified
files:
  - hub/app/api/pairing.py
  - hub/app/api/discovery.py
  - hub/app/discovery.py
  - hub/app/enrollment.py
  - node/grid_node/pairing.py
relates_to: [hub, node, data-model, dashboard-ui, users-and-roles, scheduling]
---

Two independent enrollment paths, both ending at
`enrollment.py::create_node()` (a `Node` row + bearer token — see
[data-model](data-model.md)):

- **Manual/token** (`api/pairing.py`): admin mints a one-time token from
  the dashboard (`POST /api/pairing-tokens`); node exchanges it via
  `POST /api/enroll`, run manually with `grid-node enroll --hub
  ... --token ...`. Works over WAN, no LAN required. A token can carry a
  `group` (e.g. "Lab 1") that the node created from it inherits
  automatically — the bulk-lab-enrollment path: mint one token per room,
  every machine paired with it lands in that group with no per-machine
  follow-up. Any node's group can also be changed later regardless of
  how it enrolled, via `PUT /api/nodes/{id}/group`. See
  [scheduling](scheduling.md) for the main reason groups matter
  (per-group schedule) and [data-model](data-model.md) for the schema.
  **Default schedule**: a token can also carry a `schedule` (a full
  `SchedulePolicy`), seeded onto the node's `schedule_json` the instant
  `create_node()` runs — the node's very first WebSocket connect already
  sends whatever's in `schedule_json` (see [hub](hub.md)'s `node_ws`), so
  a machine paired from a token with a schedule attached never has a
  moment of running unrestricted. Deliberately stored on the *token*, not
  the *group* — `PairingToken` is already a real row that can carry
  attributes, unlike `Node.group` (see
  [data-model](data-model.md)'s "groups have no attributes of their own"
  design note).
- **LAN discovery + 6-digit code** (`api/discovery.py` +
  `hub/app/discovery.py` on the hub side, `node/grid_node/pairing.py`
  on the node side): the expected common path. Node advertises via
  mDNS (`_grid-node._tcp.local.`) and runs a tiny local HTTP listener;
  hub browses mDNS continuously and, on `POST
  /api/discovery/{id}/pair`, dials the node directly to verify the code
  and hand over credentials. Full handshake diagram in
  `_docs/REQUIREMENTS.md` §6.
  **Bulk pairing**: `POST /api/discovery/pair-batch` (body: a list of
  `{discovery_id, code, name, group}` + an optional shared `schedule`)
  runs the same per-machine handshake (factored into
  `discovery.py::_pair_one`, shared with the single-pair endpoint) for
  several discovered machines in one request — walking through a whole
  lab's worth of unpaired machines becomes one dashboard sitting (still
  one physical code read per machine, that's inherent to the LAN
  handshake's security model, see `_docs/REQUIREMENTS.md` §6.5) instead
  of one full open/fill/close dialog cycle per machine. Tolerant per-item
  like `credentials.py`'s apply-group/apply-all: one wrong code doesn't
  abort the rest of the batch, and a prior item's successful pairing is
  never rolled back by a later item's failure (each `_pair_one` call
  commits independently).

**Verified**: both flows confirmed working end to end, including the LAN
flow's full mDNS advertise → browse → discover → direct-dial → verify →
credential-handoff → "starts running with no restart" sequence. Bulk
pairing and the token default-schedule covered by
`hub/tests/test_discovery.py`/`test_pairing.py` (partial-batch-failure
tolerance, schedule application, group-manager scoping) — not yet
exercised against real hardware in a batch (only the pre-existing
single-pair flow has a real-node live-test).

Not yet tested: a second/different network's multicast behavior (only
verified with node and hub on the same host) — still worth confirming
across two genuinely separate machines on a real LAN before fully
trusting it in a school deployment.
