# GridKeeper

[![License: MIT](https://img.shields.io/github/license/satya16/GridKeeper)](LICENSE)

A fleet hub for BOINC and Folding@home: a `grid-node` runs on each
compute machine, GridKeeper gives you one dashboard to see every
machine's status and remotely start/stop projects.

Full requirements and design: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).
How to test it: [`docs/TESTING.md`](docs/TESTING.md). Per-component
detail (what's verified, what's still open): [`knowledge-graph/`](knowledge-graph/).

## Install

Two pieces: the **hub** (one dashboard, runs anywhere) and a **node**
(one per machine you're donating cycles from).

**Hub** -- runs as a [Docker image](https://hub.docker.com/r/satya16dev/grid-hub),
on any machine with Docker (Linux, Mac, or Windows):

```bash
docker run -d -p 8000:8000 \
  -e GRIDKEEPER_ADMIN_PASSWORD=changeme \
  -e GRIDKEEPER_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  -v gridkeeper-data:/data \
  satya16dev/grid-hub:latest
```

- `GRIDKEEPER_ADMIN_PASSWORD` is the dashboard login (any username works).
- `GRIDKEEPER_SECRET_KEY` encrypts saved BOINC account keys at rest --
  keep it and reuse the same value across restarts, or any keys already
  saved become unrecoverable. Not required otherwise.
- The `-v` volume is where all real data (`grid.db`: nodes, credentials)
  lives -- without it, everything vanishes if the container is removed.
- Open it via the hub machine's **LAN IP**, not `localhost` (e.g.
  `http://192.168.1.5:8000`) -- a paired node is told to connect back to
  whatever host you used to reach the dashboard, so `localhost` would
  point a *different* machine at itself. (Or set `GRIDKEEPER_PUBLIC_URL`
  to pin this explicitly for a real deployment.)

**Node** -- runs directly on each machine's own OS, from
[PyPI](https://pypi.org/project/grid-node/). Deliberately *not*
Dockerized: its whole job is controlling the BOINC/FAHClient already
installed natively on that machine and reading real hardware sensors,
which a container would only get in the way of (bind-mounting host
binaries/sockets, `--privileged`, `--network host`) for no real benefit
-- the same reason a tool like Prometheus's `node_exporter` is normally
run natively rather than in Docker.

```bash
pipx install grid-node   # or: pip install grid-node
grid-node run
```

It prints a 6-digit pairing code and advertises itself on the LAN --
within a few seconds it shows up on the dashboard under "Discovered on
your network"; enter the code there. (No LAN/mDNS between the two, e.g.
across a VPN? Use a manual pairing token instead: dashboard -> "New
pairing token", then `grid-node enroll --hub <url> --token <token>
--name <name>`.)

Once paired, it shows up on the dashboard with live BOINC/FAH status,
start/stop controls, and CPU/RAM/temperature graphs. Hub and node can
run on the same machine too (a natural fit for a school's front-desk
machine, which then drives the dashboard *and* donates its own idle
cycles) -- pair with the manual token pointed at `localhost` rather than
LAN discovery, since that's solving a problem you don't have on one box.

Working from a repo checkout instead of an install (e.g. to run a local
change)? See [`node/README.md`](node/README.md) and
[`hub/frontend/README.md`](hub/frontend/README.md).
