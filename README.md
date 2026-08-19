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

Both paths need `GRIDKEEPER_ADMIN_PASSWORD` (any username works with the
dashboard's login, this is the password) and, to use the dashboard's
"Saved BOINC account keys" panel, `GRIDKEEPER_SECRET_KEY` (encrypts
saved keys at rest -- everything else works without it, but saving a new
key will fail). Generate one with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep that value somewhere safe and reuse it across restarts -- losing it
makes any keys already saved unrecoverable (by design: the hub only ever
stores them encrypted, never in plaintext).

Easiest: the published Docker image, no repo checkout or frontend build
needed. The `-v` volume is where `grid.db` (nodes, credentials,
everything) actually lives -- without it, data vanishes if the container
gets removed and recreated:

```bash
docker run -d -p 8000:8000 \
  -e GRIDKEEPER_ADMIN_PASSWORD=changeme \
  -e GRIDKEEPER_SECRET_KEY=<the value you generated above> \
  -v gridkeeper-data:/data \
  satya16dev/grid-hub:latest
```

Working from a repo checkout instead -- e.g. to run a local change (see
[`hub/frontend/README`](hub/frontend/README.md) for dev-mode/hot-reload
instead of a full rebuild per change):

```bash
cd hub
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..   # builds the React+Ant Design dashboard into app/static/dist/

export GRIDKEEPER_ADMIN_PASSWORD=changeme
export GRIDKEEPER_SECRET_KEY=<the value you generated above>
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

(`app/static/dist/` isn't committed, same as any other build output --
the frontend build step above is only needed once, or after pulling
frontend changes.)

Open the dashboard using the hub machine's **LAN IP**, not
`localhost` (e.g. `http://192.168.1.5:8000`) -- when you pair a node,
the hub hands it back whatever host you used to reach the dashboard so
the node knows where to connect for its normal WebSocket session; if
that was `localhost`, a *different* machine would be told to connect to
itself. (Or set `GRIDKEEPER_PUBLIC_URL` on the hub to pin this
explicitly, e.g. in the systemd/env config for a real deployment.)

Terminal 2 -- node (on the machine you want to manage -- this can be a
different machine on the LAN, or **the same machine the hub is running
on**; see below). `grid-node` is [published on PyPI](https://pypi.org/project/grid-node/),
so no repo checkout is needed on this machine at all:

```bash
pipx install grid-node   # or: pip install grid-node
grid-node run
```

(Working from a repo checkout instead -- e.g. to run a local change --
see [`node/README.md`](node/README.md) for the `pip install -e .` path.)

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

- **If running both from a repo checkout, keep separate virtualenvs.**
  `hub/` and `node/` have different dependency sets (FastAPI/SQLAlchemy/
  httpx vs. websockets/zeroconf/psutil) with some overlap -- keep them
  in their own `.venv` each rather than trying to share one. Doesn't
  apply if the hub's running via Docker and the node via `pipx install
  grid-node`, as in the Quickstart above -- there's no shared environment
  to conflict in the first place.
- **Skip LAN discovery, use the manual token instead.** LAN
  discovery/mDNS pairing works fine on a single machine too (multicast
  loopback is enabled by default on Linux), but it's solving a problem
  you don't have here -- you already have two terminals open on the same
  box. Simpler and one less moving part to debug:

  ```bash
  # dashboard -> "New pairing token" -> copy the token, then:
  grid-node enroll --hub http://localhost:8000 --token <token> --name "$(hostname)-local"
  grid-node run
  ```

The resulting node shows up on the dashboard identically to a remote
one -- same start/stop controls, same schedule policy, same live metrics.
This is a natural fit for a school's front-desk/admin machine: it drives
the dashboard *and* donates its own idle cycles, no separate always-on
box required.

## Status

v1 is functionally complete, and most of it has now been verified
against real, running BOINC/FAH installs and real project accounts, not
just mocked tests -- core system + LAN pairing (2026-08-11), FAH control
(2026-08-18), BOINC control including a real project attach and a
credential-repository feature for reusing one account key across
machines (2026-08-19). Full per-component detail, including exactly
what's automated-tested vs. manually verified vs. still open:
[`knowledge-graph/`](knowledge-graph/) -- that's the authoritative,
kept-current record; this section is a summary, not a substitute for it.

**Still open:**
- The dashboard's client-side JS/charts in an actual browser -- verified
  via its real REST API responses, not by looking at the rendered page.
- LAN pairing across two genuinely separate machines, not one host
  talking to itself.
- `apply_schedule()`'s real effect on BOINC's Activity behavior over
  time (the underlying `boinccmd` calls are verified, a live schedule
  boundary hasn't been watched being crossed).

Not yet done: TLS termination guidance for real deployments, macOS/
Windows node packaging, and GPU utilization reporting -- see "Open
questions" in the requirements doc.
