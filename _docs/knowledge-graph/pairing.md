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
relates_to: [hub, node, data-model, dashboard-ui, users-and-roles]
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
- **LAN discovery + 6-digit code** (`api/discovery.py` +
  `hub/app/discovery.py` on the hub side, `node/grid_node/pairing.py`
  on the node side): the expected common path. Node advertises via
  mDNS (`_grid-node._tcp.local.`) and runs a tiny local HTTP listener;
  hub browses mDNS continuously and, on `POST
  /api/discovery/{id}/pair`, dials the node directly to verify the code
  and hand over credentials. Full handshake diagram in
  `_docs/REQUIREMENTS.md` §6.

**Verified**: both flows confirmed working end to end, including the LAN
flow's full mDNS advertise → browse → discover → direct-dial → verify →
credential-handoff → "starts running with no restart" sequence.

Not yet tested: a second/different network's multicast behavior (only
verified with node and hub on the same host) — still worth confirming
across two genuinely separate machines on a real LAN before fully
trusting it in a school deployment.
