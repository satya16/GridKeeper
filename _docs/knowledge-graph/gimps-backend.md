---
id: gimps-backend
type: component
status: implemented-verified
files:
  - plugins/grid-node-gimps/grid_node_gimps/backend.py
relates_to: [plugin-registry, node]
---

Controls a locally-installed `mprime` (the [GIMPS](https://www.mersenne.org/)
command-line client) -- lives entirely outside this repo's `node`/`hub`
packages, in `plugins/grid-node-gimps/`, as the actual proof that
[plugin-registry](plugin-registry.md)'s entry-point mechanism works for an
unrelated developer, not a demo dressed up as a real plugin.

Unlike BOINC/FAH, mprime has no control socket/RPC for an already-running
process (confirmed live: a second `mprime -s` while one instance was
running launched a whole *second* interactive instance, not a status
query) -- so `ACTIONS` is honestly scoped to `start`/`stop` (process
launch + graceful `SIGINT`), not per-task control. No `CREDENTIAL_ACTION`
(PrimeNet account linking is a manual one-time step, same boundary
[fah-backend](fah-backend.md) draws for its passkey) and no
`SENSITIVE_FIELDS` (nothing secret in `start`/`stop`'s payload).

**Verified live** (2026-08-24): downloaded and checksum-verified real
mprime 30.19b20 from the official GIMPS mirror, drove its interactive
first-run wizard (`pexpect`, since it's a genuine multi-step Q&A UI, not
flag-driven) through "just stress testing" (no PrimeNet account) to a
real running torture-test worker -- confirmed via `ps` showing sustained
real CPU use on an actual Lucas-Lehmer computation, not simulated. Stopped
it with `SIGINT` and confirmed a clean exit (pid file removed, no
zombie). Full stack re-verified afterward through a real hub + node: the
plugin installed alongside `grid-node` with no source changes, appeared
in `discover_backends()`, its capabilities populated the hub's
`GET /api/backends` from a live status frame, and a `start` command issued
from the hub's REST API round-tripped through the WebSocket to the node
to the plugin to a real `mprime` process.

**Real bug found and fixed by this live testing**: `start()`'s
`subprocess.Popen` was never reaped, so an mprime that exits quickly
became a zombie under `grid-node`'s pid -- fixed with a daemon reaper
thread (`threading.Thread(target=proc.wait, daemon=True)`), with a
regression test (`tests/test_backend.py`) that captures the real `Popen`
object and asserts `.returncode` eventually becomes non-`None`, confirmed
to actually fail without the fix before being accepted.

**Known gap, left honest rather than papered over**: the live session
above exercised mprime's *torture test* mode (`StressTester=1`) -- a CPU/
memory stress diagnostic, not real Mersenne-search work. A bare `start()`
relaunch does not resume a torture test (it lands at mprime's interactive
Main Menu and exits almost immediately with no stdin) -- that's fine for
torture-test's actual purpose (a one-off diagnostic, not continuous work)
but means `start()`/`stop()` are verified for "launch/stop the process
cleanly," not for "correctly resume real PrimeNet search work across a
restart" (mprime's actual continuous-service mode, `UsePrimenet=1` or
manual `worktodo.txt`, per its own readme.txt, was never itself live-
tested). `get_status()` also deliberately skips parsing
`results.json.txt` for the same reason -- documented in `readme.txt` but
never observed live (torture-test mode doesn't produce it).
