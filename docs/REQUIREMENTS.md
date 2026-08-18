# Grid Manager — Requirements

A fleet manager for distributed-computing clients (BOINC and Folding@home)
running on multiple machines, with a central manager app for visibility and
remote control.

## 1. Goals

- **Primary use case**: a school (or similar org) putting a lab full of
  otherwise-idle computers to use for charitable distributed computing
  (disease research, etc. via BOINC/FAH), without competing with the
  people actually using those computers for their work. Everything below
  is shaped by that: configuration happens once, from one machine (the
  manager), across a fleet of many similar worker machines, and the
  fleet's default behavior should be "stay out of the way during active
  use, contribute when idle."
- See, from one dashboard, the status of BOINC and Folding@home (FAH) on
  every registered machine (running/paused, current work unit/task,
  progress, project, credit/points, CPU/GPU usage).
- Start or stop a specific project (or pause/resume the whole client) on a
  specific machine, remotely, from the manager.
- Configure *when* machines are allowed to run (hours of day, only while
  idle) centrally from the manager, applied to the whole fleet or
  per-machine — see section 7.
- See live CPU/RAM/temperature for every machine on one graph, with the
  ability to narrow the view to a subset of machines — see section 8.
- Support Ubuntu first. Architecture must not assume Linux-only paths so
  macOS and Windows workers can be added later without a redesign.

## 2. Non-goals (for v1)

- Installing BOINC/FAH itself on a machine (the worker assumes they're
  already installed; it only controls/monitors them).
- Multi-user accounts / RBAC (single admin user for v1).
- **Long-term historical analytics** (credit trends over weeks/months,
  metrics history that survives a manager restart) — out of scope. The
  live CPU/RAM/temperature graphs (section 8) are a short *rolling*
  window (~1 hour, in-memory only) for "what's happening right now,"
  which is a different thing and explicitly in scope.

## 3. System overview

```
 ┌─────────────┐        outbound WSS         ┌───────────────────┐
 │ grid-worker   │ ───────────────────────────▶│                    │
 │ (machine A)  │◀─────────────────────────── │   grid-manager      │
 └─────────────┘        commands + status      │  (FastAPI, SQLite)│
        │  local RPC/socket                    │                    │
        ▼                                      │  - REST API        │
 boinccmd / BOINC RPC (31416)                   │  - WebSocket hub   │
 FAHClient socket (36330)                       │  - Web dashboard   │
                                                 └───────────────────┘
                                                          ▲
                                                          │ browser (HTTPS)
                                                     admin user
```

- **grid-worker**: a small always-on service installed on each compute
  machine. It talks to the locally-installed BOINC and/or FAH clients,
  and maintains a persistent outbound WebSocket connection to the
  manager. No inbound ports need to be opened on worker machines — this
  matters because home/lab machines are often behind NAT or firewalls.
- **grid-manager**: a FastAPI app that (a) accepts worker WebSocket
  connections, tracks their live status in memory + SQLite, (b) serves a
  REST API + web dashboard for the admin, and (c) relays start/stop
  commands from the dashboard to the right worker's WebSocket connection.
- **grid-worker and grid-manager can run on the same machine.** Nothing in
  the protocol distinguishes "local" from "remote" workers — a worker's
  `manager_url` just happens to resolve to `localhost`/the loopback
  interface. This is the natural setup for the machine that hosts the
  dashboard to also donate its own idle cycles (e.g. a school's
  front-desk/admin PC), and it's the simplest possible deployment for
  trying the whole system on one box before rolling it out to a lab.

## 4. Worker (grid-worker) requirements

1. Runs as a background service (systemd unit on Ubuntu; launchd/Windows
   Service planned later) under an unprivileged user that's also in the
   `boinc` group (and can reach the FAH socket).
2. Reads a local config file (`~/.config/grid-worker/config.toml` or
   `/etc/grid-worker/config.toml`) containing: manager URL, this machine's
   display name, an auth token (issued by the manager when the worker is
   registered/paired).
3. Detects which backends are present on the machine at startup (BOINC
   installed? FAH installed?) and only activates the ones found.
4. **BOINC backend**
   - Reads client state via `boinccmd --get_state` / `--get_project_status`
     (v1) or the BOINC GUI RPC protocol on port 31416 (future, avoids
     shelling out and needs the RPC auth handshake).
   - Reports: attached projects, per-project status (running/suspended),
     current tasks and their progress %, overall run mode
     (always/auto/never), network activity mode.
   - Accepts commands: suspend/resume a specific project, suspend/resume
     the whole client, set run mode.
5. **Folding@home backend**
   - Talks to FAHClient's local control socket (default port 36330,
     text protocol returning PyON).
   - Reports: slot list, per-slot status, current work unit % progress,
     points/PPD if available.
   - Accepts commands: pause/unpause a slot, pause/unpause all, finish
     (graceful stop after current WU).
6. Sends a status snapshot to the manager on every state change, plus a
   periodic heartbeat (e.g. every 30s) so the manager can detect a
   machine going offline.
7. Reconnects with exponential backoff if the WebSocket drops; buffers
   nothing critical — on reconnect it just re-sends full current state.
8. Executes inbound commands idempotently and reports success/failure
   back to the manager per command (with a correlation id).

## 5. Manager (grid-manager) requirements

1. **Worker registry**: each worker has an id, display name, OS, list of
   detected backends (boinc/fah), last-seen timestamp, connection status
   (online/offline), and current full status snapshot.
2. **Pairing/auth**: two enrollment paths, both ending in the same place
   — a `workers` row with a bearer token the worker uses to authenticate
   its WebSocket connection:
   - **Manual/remote** (works over WAN, no LAN required): admin mints a
     one-time pairing token from the dashboard, the worker operator pastes
     it into `grid-worker enroll --manager ... --token ... --name ...`.
   - **LAN discovery + 6-digit code** (the expected common case — see
     section 6): the worker generates the code and shows it locally, the
     *admin* enters that code into the dashboard against a machine the
     manager discovered via mDNS. No token ever has to be copied onto the
     worker machine by hand.
3. **REST API** (also what the dashboard's JS calls):
   - `GET /api/workers` — list workers + live status
   - `GET /api/workers/{id}` — full detail
   - `POST /api/workers/{id}/commands` — issue a command (e.g.
     `{"backend": "boinc", "action": "resume_project", "project_url": "..."}`)
   - `GET /api/workers/{id}/commands/{cmd_id}` — command result/status
   - `POST /api/pairing-tokens` — mint a new pairing token (manual flow)
   - `GET /api/discovery` — list unpaired workers currently visible on
     the LAN via mDNS
   - `POST /api/discovery/{discovery_id}/pair` — complete pairing with a
     discovered worker using the code the admin read off that machine
   - `PUT /api/workers/{id}/schedule` — set one machine's schedule policy
   - `POST /api/schedule/apply-all` — set the same schedule policy on
     every known machine at once
   - `PUT /api/workers/{id}/group` — assign/rename/clear a machine's group
   - `GET /api/groups` — distinct group names currently in use
   - `POST /api/schedule/apply-group/{group}` — set the same schedule
     policy on every machine in one group (see §12 grouping)
4. **WebSocket hub**: `/ws/worker` endpoint workers connect to; keeps a
   map of worker_id → live connection; pushes queued commands (and
   schedule policy updates) the instant a worker is online; persists
   last-known status to SQLite so the dashboard has data even when a
   worker is offline. On every successful connect (including reconnects
   after a drop), the manager immediately re-sends that worker's stored
   schedule policy — a worker that comes back online always converges to
   the latest policy without the admin having to re-push it.
5. **Web dashboard**: server-rendered (Jinja2) page + small amount of JS
   (polling or a dashboard-side WebSocket) showing a card/table per
   machine: name, online/offline, per-backend status, schedule, and
   start/stop controls, plus a fleet-wide schedule form. No SPA framework
   needed for v1.
6. **Persistence**: SQLite via SQLAlchemy — tables for `workers` (includes
   each worker's current schedule policy as JSON), `pairing_tokens`,
   `commands` (audit log of who told what machine to do what, and the
   result). Because pairing and schedule policy both live here
   permanently, a machine paired once stays paired (and keeps whatever
   schedule was set) across manager restarts and worker reconnects — there
   is no session state that needs to be redone by hand.

## 6. LAN discovery & 6-digit code pairing

The expected day-to-day way to add a machine: start the worker on it, it
shows up on the dashboard's "Discover" list a few seconds later, admin
types in the code shown on that machine's console. No IP addresses, no
copying tokens onto the worker.

```
 worker (unpaired)                          manager (grid-manager)
 ──────────────────                         ────────────────────
 grid-worker run
   no config.toml found
   → generate 6-digit code, print it
   → advertise via mDNS (_grid-worker._tcp.local,
     TXT: hostname, backends)
   → tiny local HTTP listener (random port)
                                             admin opens dashboard's
                                             Discover panel, sees the
                                             worker (via mDNS browse)
                                             admin types in the code
                                                     │
                              POST http://<worker-ip>:<port>/pair
                              {"code": "482913"}         │
                              ◀─────────────────────────┘
   verify code (TTL + attempt limit)
   200 {name, os_name, backends}  ─────────────────────▶
                                             manager creates the Worker
                                             row, mints a bearer token
                              POST .../pair-complete
                              {worker_id, bearer_token,
                               manager_url, name}          │
                              ◀─────────────────────────┘
   writes config.toml, stops mDNS
   advertising + pairing listener,
   proceeds straight into the normal
   WebSocket run loop (no restart)
```

1. A worker with no `config.toml` starts in **pairing mode** rather than
   failing: it generates a random 6-digit numeric code, valid for 10
   minutes or 5 failed verification attempts (whichever comes first;
   either one triggers a fresh code), and prints it to stdout/journalctl
   plus writes it to `~/.config/grid-worker/pairing_code.txt` so
   `grid-worker status` can show it on demand without tailing logs.
2. The worker advertises itself over mDNS as `_grid-worker._tcp.local.`
   with TXT records for hostname and detected backends (never the code
   itself — mDNS traffic is broadcast to the whole LAN segment).
3. The worker's local pairing HTTP listener binds an OS-assigned port on
   the LAN interface and exposes exactly two endpoints, unauthenticated
   apart from the code check itself:
   - `POST /pair {"code": "..."}` — validates against the current code;
     wrong code increments an attempt counter (1s throttle per miss);
     expired or exhausted regenerates and logs a new code. Returns the
     worker's self-reported name/os/backends on success so the manager
     doesn't need a second round trip to learn them.
   - `POST /pair-complete {"worker_id", "bearer_token", "manager_url", "name"}` —
     only accepted after a successful `/pair` in the same process
     lifetime; `name` is the manager's final decision (the admin's
     override if they gave one during pairing, else the worker's own
     self-reported name from `/pair`) so the worker's local config and
     the manager's dashboard never disagree on what to call it. Writes
     `config.toml` and signals the main loop to drop pairing mode and
     connect normally.
4. The manager browses mDNS continuously (`GET /api/discovery` reflects
   what it currently sees) and, on `POST /api/discovery/{id}/pair`,
   is the one that dials the worker directly over the LAN to run the
   two-step handshake above — the browser/admin never talks to the
   worker directly.
5. Security posture is intentionally closer to "smart-home device
   pairing" than a general auth system: 6 digits is a 1-in-1,000,000
   guess, throttled to 5 attempts per 10-minute code window. That's
   adequate for a trusted home/lab LAN where the threat model is
   "someone plugs in a laptop on my network," not adequate if the LAN
   itself is hostile. The manual token flow (section 5.2) remains
   available for anything more exposed, e.g. pairing over a VPN/WAN link.

## 7. Centralized scheduling (hours / idle-only)

The point of this project is putting *idle* time to use, not competing
with whoever's sitting at the machine — so the manager needs to be able to
say "only donate cycles overnight" or "only when nobody's using it,"
configured once and applied everywhere.

A `SchedulePolicy` (`enabled`, `restrict_hours` + `active_start_hour`/
`active_end_hour`, `only_when_idle` + `idle_threshold_minutes`) is set on
the manager — either per-machine (each worker card's "Schedule" section) or
fleet-wide in one shot (`POST /api/schedule/apply-all`, the expected path
for a lab of near-identical machines). It's stored on the `workers` row
and pushed to the worker as a `{"type": "schedule", ...}` WebSocket
frame, both immediately (if the worker's online) and again automatically
every time that worker (re)connects.

**Enforcement deliberately differs by backend, because BOINC already
solves this and FAH doesn't:**

- **BOINC** has its own mature idle-detection and hour-of-day scheduling
  built into the client (`global_prefs_override.xml`: `run_if_user_active`,
  `idle_time_to_run`, `start_hour`/`end_hour`). On receiving a schedule
  frame, the worker writes this file once (via `boinccmd
  --set_global_prefs_override` + `--read_global_prefs_override`) and lets
  BOINC's own daemon enforce it continuously — no polling loop needed on
  our side, and BOINC's idle detection is more mature than anything we'd
  build ourselves.
- **Folding@home** has no equivalent native mechanism, so the worker
  enforces the policy itself: a loop checks the policy every 60 seconds
  (or immediately on a policy change) and calls FAH's pause/unpause-all
  accordingly. Hour restrictions are a simple clock check (reliable);
  idle detection is best-effort via systemd-logind's `IdleHint`
  (`loginctl`) — not guaranteed available on every machine (headless, no
  active login session, non-systemd), and fails *open* (treats "can't
  tell" as idle) rather than silently blocking FAH from ever running.
- This FAH enforcement loop runs independently of the WebSocket
  connection lifecycle, not nested inside it — a network blip must not
  suspend schedule enforcement along with the connection.

## 8. Live system metrics (CPU / RAM / temperature)

Every status frame the worker sends now also carries a `metrics` block
(`cpu_percent`, `ram_percent`, `temperature_c`), collected via `psutil`.
The manager keeps an in-memory rolling window per worker (~1 hour at the
default 10s poll interval; not written to SQLite — see the Non-goals
note in section 2) and exposes it as `GET /api/metrics`.

The dashboard renders this as **three separate line charts** — CPU%,
RAM%, temperature °C — never combined onto one chart with a second axis,
since they're different scales and dual-axis charts are misleading by
construction. All three share:

- A **device filter row** above the charts (checkboxes, "All"/"None"),
  scoping all three charts identically — the point of "filter to only
  view some of them."
- A **fixed color per device**, assigned from an 8-slot categorical
  palette and stable across re-renders and filter changes — deselecting
  one device never repaints another's line a different color. Because
  the palette only has 8 slots that stay distinguishable under
  colorblindness simulation, a 9th device simply can't be graphed
  simultaneously — its filter pill is disabled with an explanatory
  tooltip rather than silently reusing a color or drawing an
  indistinguishable line. (This is a real constraint for a lab with more
  than 8 machines: the filter is how you work within it, not a
  cosmetic option.)
- A **shared crosshair + tooltip**: hovering anywhere on a chart shows
  every visible device's value at that moment, not just whichever line
  the cursor happens to be over.
- A legend (always present once ≥2 devices are shown), gridlines, and
  2px lines, per the house chart-design rules the rest of a well-built
  dashboard would follow.

Implementation notes: no charting library — hand-rolled inline SVG,
consistent with the dashboard's existing zero-build-step, no-SPA-framework
approach. Temperature reporting is effectively Linux-only for now
(`psutil.sensors_temperatures()` isn't implemented on macOS/Windows) and
degrades to `null`/omitted rather than erroring — same "fail open, log
once" pattern as the rest of this codebase's platform-specific bits.

## 9. Security

- All worker↔manager traffic over TLS in production (WSS). For local dev,
  plain WS is fine.
- Workers authenticate with a bearer token, not IP allowlisting (laptops
  move networks).
- The dashboard itself should sit behind at minimum HTTP basic auth or a
  single admin password for v1; proper auth can come later.
- Commands are logged (who/when/what/result) for auditability.

## 10. Tech stack (decided)

- **Language**: Python throughout (worker + manager).
- **Manager**: FastAPI, Uvicorn, SQLAlchemy + SQLite, Jinja2 templates,
  native `websockets`/FastAPI WebSocket support, `httpx` (async client
  used to dial workers directly during LAN pairing), `zeroconf`
  (`AsyncZeroconf`, browses mDNS for unpaired workers).
- **Worker**: Python, `websockets` client, `tomllib` for config,
  subprocess wrapper around `boinccmd`, raw `socket` client for FAH's
  text/PyON protocol, `zeroconf` (registers the pairing mDNS service),
  stdlib `http.server` for the tiny local pairing listener (kept off
  a heavier web framework since it only ever needs two endpoints).
- **Transport**: persistent outbound WebSocket from worker to manager
  (chosen over polling for instant command delivery and no open inbound
  ports on worker machines).
- **Discovery**: mDNS/DNS-SD via the pure-Python `zeroconf` library —
  no OS-level daemon dependency (unlike relying on Avahi directly), and
  it works the same way once macOS/Windows workers exist.
- **Scheduling**: no new dependency — BOINC's own `global_prefs_override.xml`
  mechanism (via `boinccmd`) for BOINC, stdlib `subprocess` calling
  `loginctl` (systemd-logind) for best-effort FAH idle detection, stdlib
  `datetime` for hour-of-day checks.
- **Metrics**: `psutil` (worker, CPU/RAM/temperature collection); no new
  manager dependency (in-memory `collections.deque`) or frontend
  dependency (hand-rolled inline SVG charts, same as the rest of the
  dashboard).

## 11. Platform roadmap

| Platform | Worker status |
|----------|---------------|
| Ubuntu   | v1 target — systemd service, `boinccmd` on PATH, FAH default socket port |
| macOS    | planned — launchd plist, same Python codebase, path differences only |
| Windows  | planned — Windows Service (via `pywin32` or NSSM wrapper), same codebase |

The worker's OS-specific bits (service install, default paths) are
isolated behind a small `platform/` module so the BOINC/FAH backend
logic itself stays OS-agnostic.

**Packaging as installable `.deb`s (decision pending, not yet built):**
confirmed feasible without full Debian packaging tooling — `dpkg-deb`
alone is enough to build a real, installable package; no need to run the
apps themselves to package them, so this isn't blocked by the pending
venv setup (section on top of this file / `CLAUDE.md`). `.deb` over Snap
for `grid-worker` specifically, since Snap's confinement model fights its
need for unsandboxed system access (`boinccmd`, FAH's raw socket,
`loginctl`, mDNS/UDP); `grid-manager` is a plain web service and could go
either way. Open question: satisfy Python dependencies via **apt
`Depends`** (lighter, but version availability varies by Ubuntu release —
riskiest for FastAPI/Starlette on older releases) or a **vendored venv
inside the package** (heavier, but reproduces `requirements.txt` exactly
regardless of target Ubuntu version). Also note: there's currently no
systemd unit for `grid-manager` itself, only for `grid-worker` — needed
before packaging the manager.

## 12. Open questions

- Do we want per-project remote *attach* (adding a brand-new BOINC
  project to a machine that isn't attached to it yet), or only
  start/stop of already-attached projects? (v1 assumes the latter.)
- GPU utilization reporting — pull from `nvidia-smi`/`rocm-smi` later?
- ~~Should the dashboard support grouping machines (e.g. "Lab 1",
  "Library")~~ — **built**: `Worker.group`/`PairingToken.group`,
  `PUT /api/workers/{id}/group`, `GET /api/groups`, and
  `POST /api/schedule/apply-group/{group}` for per-room hours. See
  `knowledge-graph/data-model.md`, `pairing.md`, `scheduling.md`,
  `dashboard-ui.md`. Grouping is currently schedule-only — extending
  group-scoped *commands* (e.g. "suspend all of Lab 1") beyond schedule
  is still open if that turns out to matter in practice.
- Bulk *pairing* (walking through several discovered-but-unpaired
  machines in one dashboard flow) instead of one code at a time — matters
  more once someone's onboarding a whole lab in one sitting rather than
  adding a machine or two.
