# grid-worker

The worker half of Grid Manager. Runs on each machine that has BOINC and/or
Folding@home (FAHClient) installed, reports their status to a `grid-manager`,
and executes start/stop commands issued from the manager's dashboard.

See [`../docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) for the full design.

## Install (Ubuntu)

```bash
cd worker
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

`grid-worker run` works before this machine has ever been paired: if there's
no config yet, it enters pairing mode automatically instead of erroring.

```bash
grid-worker run
```

It will print a 6-digit code and advertise itself on the local network via
mDNS:

```
=== Pairing code: 482913 (valid 10 min) -- enter this in the Grid Manager dashboard ===
```

On the manager's dashboard, the machine shows up under "Discovered on your
network" within a few seconds. Type the code into that card and submit --
the manager dials this machine directly over the LAN, verifies the code,
and hands it a bearer token. The same `grid-worker run` process then
continues straight into normal operation, no restart needed.

If you're at the machine but the code has scrolled off, or you're checking
on it via SSH without wanting to tail logs:

```bash
grid-worker status
```

As a systemd service (recommended for real use -- pairing mode works the
same way under systemd, just check `journalctl` for the code):

```bash
sudo cp packaging/systemd/grid-worker.service "/etc/systemd/system/grid-worker@$USER.service"
sudo systemctl daemon-reload
sudo systemctl enable --now "grid-worker@$USER"
journalctl -u "grid-worker@$USER" -f
```

## Enroll manually instead (no LAN / no mDNS)

For a machine that isn't on the same LAN segment as the manager (e.g. over
a VPN, or mDNS is blocked on your network), pair with a manager-generated
token instead -- the admin mints the token on the dashboard and it's typed
into the *worker* this time, the reverse of the LAN flow above:

```bash
grid-worker enroll --manager http://<manager-host>:8000 --token <pairing-token> --name "<machine-name>"
```

This writes `~/.config/grid-worker/config.toml` directly (mode 600 -- it
holds a bearer token) and detects which backends (BOINC/FAH) are present,
skipping pairing mode on the next `grid-worker run`.

## Local status page (optional, off by default)

Workers run headless by design -- fine for a bulk-enrolled lab machine
managed from the dashboard, less fine if someone's sitting at that PC and
wants to see what it's doing without going to find the dashboard. Turn on
a small read-only status page, local to that machine only:

```bash
grid-worker local-ui enable          # optionally: --port 8420 (default)
grid-worker local-ui status          # check whether it's on
grid-worker local-ui disable
```

Takes effect the next time `grid-worker run` starts. Reachable only at
`http://127.0.0.1:<port>/` on that same machine (never the LAN) -- shows
connection state, backend status/progress, live CPU/RAM/temperature, and
schedule state, refreshing every 10s. Read-only: no controls here,
pausing/resuming stays a manager-dashboard action.

## Notes

- Runs fine on the same machine as `grid-manager` -- see "Running the
  worker on the same machine as the manager" in the top-level
  [README](../README.md) for the recommended setup (separate venvs, use
  the manual token flow instead of LAN discovery since you don't need it
  locally).
- The worker only *controls* BOINC/FAH -- it does not install them. Install
  `boinc-client` (or the BOINC snap) and/or FAHClient yourself first. It
  can, however, attach/detach a BOINC *project* once BOINC itself is
  installed -- from the dashboard, per machine (needs that project's
  account key, from the project's "your account" web page; BOINC doesn't
  create accounts for you). FAH has no per-project concept -- the closest
  equivalent, also settable from the dashboard, is picking a `cause`
  (e.g. cancer, COVID-19) and optionally linking an account (username/
  team/passkey) or folding anonymously.
- If neither is detected at startup, the worker still connects and reports
  an empty status; re-run detection by restarting the worker after
  installing BOINC/FAH.
- The BOINC backend shells out to `boinccmd`; the FAH backend speaks
  JSON over WebSocket to FAHClient's local API directly (`ws://127.0.0.1:7396/api/websocket`,
  the current `fah-client` 8.x -- not the older FAHClient v7 socket
  protocol) -- see the docstrings in `grid_worker/backends/boinc.py` and
  `fah.py` if their output format differs on your installed version and
  the parser needs adjusting.
- Pairing mode opens an unauthenticated (apart from the 6-digit code)
  HTTP listener on an OS-assigned port, bound to all interfaces, plus an
  mDNS advertisement -- fine on a trusted home/lab LAN, not something to
  expose past a firewall. See "LAN discovery & 6-digit code pairing" in
  `docs/REQUIREMENTS.md` for the exact security posture.
- The mDNS registration in `pairing.py` has been confirmed working (a
  worker advertising and a manager discovering/pairing it on the same
  host) -- not yet tested across two genuinely separate machines. If the
  manager's "Discovered on your network" list doesn't pick up a waiting
  worker across a real LAN, check `avahi-browse -a` (or similar) to
  confirm the service is actually being advertised before assuming the
  app logic is wrong.
- CPU%, RAM%, and (Linux-only, best-effort) temperature are collected via
  `psutil` and sent with every status update, feeding the dashboard's
  "Live metrics" graphs -- nothing to configure, it's automatic once the
  worker is running.
- Schedule policies pushed from the dashboard ("Fleet schedule" / a
  machine's own "Schedule" section) are applied automatically: BOINC gets
  its own native preferences file rewritten (`boinccmd
  --set_global_prefs_override`), FAH gets paused/resumed by the worker
  itself on a 60s check loop. The policy push/persist/reconnect path is
  confirmed working; the actual `boinccmd`/FAH enforcement calls have not
  been exercised against a live BOINC/FAH install yet.
