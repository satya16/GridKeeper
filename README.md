# GridKeeper

[![License: MIT](https://img.shields.io/github/license/satya16/GridKeeper)](LICENSE)

A fleet hub for BOINC and Folding@home: a `grid-node` runs on each
compute machine, GridKeeper gives you one dashboard to see every
machine's status and remotely start/stop projects.

Full requirements and design: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).
How to test it (automated suite + manual checklist): [`docs/TESTING.md`](docs/TESTING.md).

- [`hub/`](hub/) -- FastAPI dashboard + REST API + WebSocket server
- [`node/`](node/) -- `grid-node`, the per-machine service (see its
  [README](node/README.md) for install/enroll/run instructions)

## Quickstart

Terminal 1 -- hub:

```bash
cd hub
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..   # builds the React+Ant Design dashboard into app/static/dist/

export GRIDKEEPER_ADMIN_PASSWORD=changeme   # set your own
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

To save BOINC project account keys and re-apply them to any machine from
the dashboard instead of pasting a key into each machine's attach form,
also set `GRIDKEEPER_SECRET_KEY` (used to encrypt saved keys at rest --
without it, everything else works, but the dashboard's "Saved BOINC
account keys" panel will fail to save a new key):

```bash
export GRIDKEEPER_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

Keep this value somewhere safe -- losing it makes any keys already saved
unrecoverable (by design: the hub only ever stores them encrypted,
never in plaintext).

The frontend build step is only needed once (or after pulling frontend
changes) -- `app/static/dist/` isn't committed, same as any other build
output; see [`hub/frontend/README`](hub/frontend/README.md) for
dev-mode (hot reload) instead of a full rebuild per change.

Open the dashboard using the hub machine's **LAN IP**, not
`localhost` (e.g. `http://192.168.1.5:8000`) -- when you pair a node,
the hub hands it back whatever host you used to reach the dashboard so
the node knows where to connect for its normal WebSocket session; if
that was `localhost`, a *different* machine would be told to connect to
itself. (Or set `GRIDKEEPER_PUBLIC_URL` on the hub to pin this
explicitly, e.g. in the systemd/env config for a real deployment.)
Any username works, password = `GRIDKEEPER_ADMIN_PASSWORD`.

Terminal 2 -- node (on the machine you want to manage -- this can be a
different machine on the LAN, or **the same machine the hub is running
on**; see below):

```bash
cd node
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
grid-node run
```

It'll print a 6-digit pairing code and advertise itself on the LAN. Within
a few seconds it shows up on the dashboard under "Discovered on your
network" -- type the code into that card and submit. The same `grid-node
run` process then continues straight into normal operation.

(No LAN/mDNS between the two, e.g. testing across a VPN? Use the manual
token flow instead: click "New pairing token" on the dashboard, then
`grid-node enroll --hub ... --token ... --name ...` on the node side
-- see [`node/README.md`](node/README.md) for details.)

Refresh the dashboard -- the machine should show as online, with BOINC/FAH
status once it detects them. Set an hours/idle schedule per-machine or for
the whole fleet under "Fleet schedule," and watch live CPU/RAM/temperature
under "Live metrics" (use the device checkboxes there to narrow the graph
to specific machines).

## Running the node on the same machine as the hub

Fully supported, and arguably the easiest way to try this out: nothing in
the node/hub split assumes they're on different hosts, since they
only ever talk over HTTP/WebSocket to `hub_url`. There's no
"same-machine" special case in the code, and none is needed -- `hub_url`
just happens to resolve to `localhost`.

Two things worth knowing for this setup specifically:

- **Separate virtualenvs, same machine.** `hub/` and `node/` have
  different dependency sets (FastAPI/SQLAlchemy/httpx vs.
  websockets/zeroconf/psutil) with some overlap -- keep them in their own
  `.venv` each, as in the Quickstart above, rather than trying to share
  one.
- **Skip LAN discovery, use the manual token instead.** LAN
  discovery/mDNS pairing works fine on a single machine too (multicast
  loopback is enabled by default on Linux), but it's solving a problem
  you don't have here -- you already have two terminals open on the same
  box. Simpler and one less moving part to debug:

  ```bash
  # dashboard -> "New pairing token" -> copy the token, then:
  cd node && grid-node enroll --hub http://localhost:8000 --token <token> --name "$(hostname)-local"
  grid-node run
  ```

The resulting node shows up on the dashboard identically to a remote
one -- same start/stop controls, same schedule policy, same live metrics.
This is a natural fit for a school's front-desk/admin machine: it drives
the dashboard *and* donates its own idle cycles, no separate always-on
box required.

## Status

v1 is functionally complete and has passed a first real smoke test
(2026-08-11, local): hub boot, auth, all REST endpoints, both
pairing flows (**including LAN/mDNS discovery, which worked end to end
on the first attempt**), the full node↔hub WebSocket protocol,
node restart/reconnect with schedule-policy persistence, and live
`psutil` metrics collection all confirmed working. One real bug found
and fixed along the way (a node-name override during LAN pairing
wasn't propagated back to the node's own config). Full per-component
detail: [`knowledge-graph/`](knowledge-graph/).

**Still open** (the smoke test ran on a machine with no BOINC/FAH
installed and no display):
- Actual BOINC/FAH command execution and `apply_schedule()` against a
  real install -- only the graceful-failure path was confirmed.
- The dashboard's client-side JS/charts in an actual browser.
- LAN pairing across two genuinely separate machines, not one host
  talking to itself.

Not yet done: TLS termination guidance for real deployments,
macOS/Windows node packaging, GPU utilization reporting, and
machine grouping / bulk pairing for larger deployments -- see "Open
questions" in the requirements doc.
