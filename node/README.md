# grid-node

The node half of GridKeeper. Runs on each machine that has BOINC and/or
Folding@home (FAHClient) installed, reports their status to GridKeeper,
and executes start/stop commands issued from the hub's dashboard.

See [`../_docs/REQUIREMENTS.md`](../_docs/REQUIREMENTS.md) for the full design.

## Install (Ubuntu)

```bash
cd node
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Make sure your user can control BOINC locally:

```bash
sudo adduser "$USER" boinc   # lets boinccmd talk to the local BOINC client
# log out/in (or `newgrp boinc`) for the group change to take effect
```

FAHClient (`fah-client` 8.x)'s local API is open to any local user by
default, so no extra group is needed for Folding@home.

## Run + pair (LAN, the normal path)

`grid-node run` works before this machine has ever been paired: if there's
no config yet, it enters pairing mode automatically instead of erroring.

```bash
grid-node run
```

It will print a 6-digit code and advertise itself on the local network via
mDNS:

```
=== Pairing code: 482913 (valid 10 min) -- enter this in the GridKeeper dashboard ===
```

On the hub's dashboard, the machine shows up under "Discovered on your
network" within a few seconds. Type the code into that card and submit --
the hub dials this machine directly over the LAN, verifies the code,
and hands it a bearer token. The same `grid-node run` process then
continues straight into normal operation, no restart needed.

If you're at the machine but the code has scrolled off, or you're checking
on it via SSH without wanting to tail logs:

```bash
grid-node status
```

As a systemd service (recommended for real use -- pairing mode works the
same way under systemd, just check `journalctl` for the code):

```bash
sudo cp packaging/systemd/grid-node.service "/etc/systemd/system/grid-node@$USER.service"
sudo systemctl daemon-reload
sudo systemctl enable --now "grid-node@$USER"
journalctl -u "grid-node@$USER" -f
```

## Enroll manually instead (no LAN / no mDNS)

For a machine that isn't on the same LAN segment as the hub (e.g. over
a VPN, or mDNS is blocked on your network), pair with a hub-generated
token instead -- the admin mints the token on the dashboard and it's typed
into the *node* this time, the reverse of the LAN flow above:

```bash
grid-node enroll --hub http://<hub-host>:8000 --token <pairing-token> --name "<machine-name>"
```

This writes `~/.config/grid-node/config.toml` directly (mode 600 -- it
holds a bearer token) and detects which backends (BOINC/FAH) are present,
skipping pairing mode on the next `grid-node run`.

## Local status page (optional, off by default)

Nodes run headless by design -- fine for a bulk-enrolled lab machine
managed from the dashboard, less fine if someone's sitting at that PC and
wants to see what it's doing without going to find the dashboard. Turn on
a small read-only status page, local to that machine only:

```bash
grid-node local-ui enable          # optionally: --port 8420 (default)
grid-node local-ui status          # check whether it's on
grid-node local-ui disable
```

Takes effect the next time `grid-node run` starts. Reachable only at
`http://127.0.0.1:<port>/` on that same machine (never the LAN) -- shows
connection state, backend status/progress, live CPU/RAM/temperature, and
schedule state, refreshing every 10s. Read-only: no controls here,
pausing/resuming stays a hub-dashboard action.

## Notes

- Runs fine on the same machine as GridKeeper -- see "Running the
  node on the same machine as the hub" in the top-level
  [README](../README.md) for the recommended setup (separate venvs, use
  the manual token flow instead of LAN discovery since you don't need it
  locally).
- The node only *controls* BOINC/FAH -- it does not install them. Install
  `boinc-client` (or the BOINC snap) and/or FAHClient yourself first. It
  can, however, attach/detach a BOINC *project* once BOINC itself is
  installed -- from the dashboard, per machine (needs that project's
  account key, from the project's "your account" web page; BOINC doesn't
  create accounts for you). FAH has no per-project concept -- the closest
  equivalent, also settable from the dashboard, is picking a `cause`
  (e.g. cancer, COVID-19) and optionally linking an account (username/
  team/passkey) or folding anonymously.
- If neither is detected at startup, the node still connects and reports
  an empty status; re-run detection by restarting the node after
  installing BOINC/FAH.
- The BOINC backend shells out to `boinccmd`; the FAH backend speaks
  JSON over WebSocket to FAHClient's local API directly (`ws://127.0.0.1:7396/api/websocket`,
  the current `fah-client` 8.x -- not the older FAHClient v7 socket
  protocol) -- see the docstrings in `grid_node/backends/boinc.py` and
  `fah.py` if their output format differs on your installed version and
  the parser needs adjusting.
- Pairing mode opens an unauthenticated (apart from the 6-digit code)
  HTTP listener on an OS-assigned port, bound to all interfaces, plus an
  mDNS advertisement -- fine on a trusted home/lab LAN, not something to
  expose past a firewall. See "LAN discovery & 6-digit code pairing" in
  `_docs/REQUIREMENTS.md` for the exact security posture.
- The mDNS registration in `pairing.py` has been confirmed working (a
  node advertising and a hub discovering/pairing it on the same
  host) -- not yet tested across two genuinely separate machines. If the
  hub's "Discovered on your network" list doesn't pick up a waiting
  node across a real LAN, check `avahi-browse -a` (or similar) to
  confirm the service is actually being advertised before assuming the
  app logic is wrong.
- CPU%, RAM%, and (Linux-only, best-effort) temperature are collected via
  `psutil` and sent with every status update, feeding the dashboard's
  "Live metrics" graphs -- nothing to configure, it's automatic once the
  node is running.
- Schedule policies pushed from the dashboard ("Fleet schedule" / a
  machine's own "Schedule" section) are applied automatically: BOINC gets
  its own native preferences file rewritten (`boinccmd
  --set_global_prefs_override`), FAH gets paused/resumed by the node
  itself on a 60s check loop. The policy push/persist/reconnect path is
  confirmed working, and so are the underlying commands each side uses
  (BOINC's `suspend_all`/`resume_all`, FAH's `pause`/`unpause`) against
  live installs -- what's not yet verified is `apply_schedule()`'s
  `global_prefs_override.xml` actually changing BOINC's real Activity
  behavior, or watching FAH's 60s enforcement loop cross a real
  hours/idle boundary live.
