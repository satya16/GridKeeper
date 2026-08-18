# Grid Manager

[![License: MIT](https://img.shields.io/github/license/satya16/GridKeeper)](LICENSE)

A fleet manager for BOINC and Folding@home: a `grid-worker` runs on each
compute machine, a `grid-manager` gives you one dashboard to see every
machine's status and remotely start/stop projects.

Full requirements and design: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).
How to test it (automated suite + manual checklist): [`docs/TESTING.md`](docs/TESTING.md).

- [`manager/`](manager/) -- FastAPI dashboard + REST API + WebSocket hub
- [`worker/`](worker/) -- `grid-worker`, the per-machine service (see its
  [README](worker/README.md) for install/enroll/run instructions)

## Quickstart

Terminal 1 -- manager:

```bash
cd manager
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..   # builds the React+Ant Design dashboard into app/static/dist/

export GRID_MANAGER_ADMIN_PASSWORD=changeme   # set your own
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The frontend build step is only needed once (or after pulling frontend
changes) -- `app/static/dist/` isn't committed, same as any other build
output; see [`manager/frontend/README`](manager/frontend/README.md) for
dev-mode (hot reload) instead of a full rebuild per change.

Open the dashboard using the manager machine's **LAN IP**, not
`localhost` (e.g. `http://192.168.1.5:8000`) -- when you pair a worker,
the manager hands it back whatever host you used to reach the dashboard so
the worker knows where to connect for its normal WebSocket session; if
that was `localhost`, a *different* machine would be told to connect to
itself. (Or set `GRID_MANAGER_PUBLIC_URL` on the manager to pin this
explicitly, e.g. in the systemd/env config for a real deployment.)
Any username works, password = `GRID_MANAGER_ADMIN_PASSWORD`.

Terminal 2 -- worker (on the machine you want to manage -- this can be a
different machine on the LAN, or **the same machine the manager is running
on**; see below):

```bash
cd worker
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
grid-worker run
```

It'll print a 6-digit pairing code and advertise itself on the LAN. Within
a few seconds it shows up on the dashboard under "Discovered on your
network" -- type the code into that card and submit. The same `grid-worker
run` process then continues straight into normal operation.

(No LAN/mDNS between the two, e.g. testing across a VPN? Use the manual
token flow instead: click "New pairing token" on the dashboard, then
`grid-worker enroll --manager ... --token ... --name ...` on the worker side
-- see [`worker/README.md`](worker/README.md) for details.)

Refresh the dashboard -- the machine should show as online, with BOINC/FAH
status once it detects them. Set an hours/idle schedule per-machine or for
the whole fleet under "Fleet schedule," and watch live CPU/RAM/temperature
under "Live metrics" (use the device checkboxes there to narrow the graph
to specific machines).

## Running the worker on the same machine as the manager

Fully supported, and arguably the easiest way to try this out: nothing in
the worker/manager split assumes they're on different hosts, since they
only ever talk over HTTP/WebSocket to `manager_url`. There's no
"same-machine" special case in the code, and none is needed -- `manager_url`
just happens to resolve to `localhost`.

Two things worth knowing for this setup specifically:

- **Separate virtualenvs, same machine.** `manager/` and `worker/` have
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
  cd worker && grid-worker enroll --manager http://localhost:8000 --token <token> --name "$(hostname)-local"
  grid-worker run
  ```

The resulting worker shows up on the dashboard identically to a remote
one -- same start/stop controls, same schedule policy, same live metrics.
This is a natural fit for a school's front-desk/admin machine: it drives
the dashboard *and* donates its own idle cycles, no separate always-on
box required.

## Status

v1 is functionally complete and has passed a first real smoke test
(2026-08-11, local): manager boot, auth, all REST endpoints, both
pairing flows (**including LAN/mDNS discovery, which worked end to end
on the first attempt**), the full worker↔manager WebSocket protocol,
worker restart/reconnect with schedule-policy persistence, and live
`psutil` metrics collection all confirmed working. One real bug found
and fixed along the way (a worker-name override during LAN pairing
wasn't propagated back to the worker's own config). Full per-component
detail: [`knowledge-graph/`](knowledge-graph/).

**Still open** (the smoke test ran on a machine with no BOINC/FAH
installed and no display):
- Actual BOINC/FAH command execution and `apply_schedule()` against a
  real install -- only the graceful-failure path was confirmed.
- The dashboard's client-side JS/charts in an actual browser.
- LAN pairing across two genuinely separate machines, not one host
  talking to itself.

Not yet done: TLS termination guidance for real deployments,
macOS/Windows worker packaging, GPU utilization reporting, and
machine grouping / bulk pairing for larger deployments -- see "Open
questions" in the requirements doc.
