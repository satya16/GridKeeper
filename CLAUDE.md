# GridKeeper — working notes

See [`_docs/REQUIREMENTS.md`](_docs/REQUIREMENTS.md) for the full design,
[`README.md`](README.md) for the quickstart, and
[`_docs/TESTING.md`](_docs/TESTING.md) for how to test it.

## Testing

There's now a real automated test suite — `hub/tests/` (52 tests:
FastAPI `TestClient` + temp SQLite, WebSocket layer mocked) and
`node/tests/` (53 tests: pure logic, all I/O mocked) — 105 total. Run
both before trusting a change:

```bash
cd hub && source .venv/bin/activate && pytest tests/ -v
cd node  && source .venv/bin/activate && pytest tests/ -v
```

**When you touch code these tests cover, run them. When you add a new
endpoint or a new piece of non-trivial logic, add a test for it** — this
project has no CI yet, so "I ran it once by hand" is the only signal
until someone runs `pytest` again, and that signal decays fast. Full
breakdown of what's covered vs. what still needs real hardware/a browser:
`_docs/TESTING.md`.

## Knowledge graph

[`_docs/knowledge-graph/`](_docs/knowledge-graph/) is a navigation layer over the
codebase: one short markdown file per component/data-model/protocol
(hub, node, pairing, scheduling, metrics, the two backends,
dashboard-ui, data-model, wire-protocol), each with a `relates_to` list
of the other entities it touches. Start there — `_docs/knowledge-graph/README.md`
first — when orienting in this project cold, especially once it's grown
past what fits in one read-through of `_docs/REQUIREMENTS.md`. It's a
map, not the territory: entries point into real file paths and
`_docs/REQUIREMENTS.md`/`CLAUDE.md` for detail rather than restating it.

**Keep it current.** Add an entity when a genuinely new subsystem shows
up; update an existing one when its behavior changes meaningfully
(especially its `status` — see the status vocabulary in
`_docs/knowledge-graph/README.md` — the first time something actually gets
runtime-verified, flip it there). A stale knowledge graph actively
misleads, since it reads as authoritative; don't let entries drift from
what `_docs/REQUIREMENTS.md` and the code actually say.

## Verified 2026-08-11: core system + LAN pairing work end to end

The `python3.14-venv` sudo blocker is resolved. First real runtime smoke
test happened this session, locally (node and hub as separate
processes/venvs on the same machine, no BOINC/FAH installed). Confirmed
working: hub boot, auth gate, all REST endpoints, dashboard HTML/JS
serving, both pairing flows (**including the previously-highest-risk
LAN/mDNS discovery path — worked on the first real attempt**), the full
WebSocket wire protocol (status/command/command_result/schedule frames),
node restart-and-reconnect with no re-enrollment, and schedule-policy
persistence across a reconnect. Per-entity detail and exact verification
notes: [`_docs/knowledge-graph/`](_docs/knowledge-graph/) (each entity's `status` and
"Verified"/"Partially verified" paragraph) — that's now the authoritative
record of what's confirmed vs. still open, more precise than this file.

One real bug found and fixed by actually running it: `/pair-complete`
didn't send back the hub's *final* chosen node name (which can
differ from the node's self-reported one if the admin overrides it
during pairing), so the node's local `config.toml` could permanently
disagree with the dashboard. Fixed in both `node/grid_node/pairing.py`
and `hub/app/api/discovery.py`.

**Still genuinely unverified** (the test environment couldn't exercise
these — see the relevant `_docs/knowledge-graph/` entity for specifics):
- Actual BOINC/FAH interaction. BOINC specifically was *attempted* on real
  hardware on 2026-08-13 and hit a real blocker, not just "not installed"
  — Ubuntu's `boinc-client` package has a reproducible, inconsistent GUI
  RPC daemon bug (confirmed across a clean purge+reinstall, AppArmor ruled
  out), and the snap alternative doesn't ship `boinccmd`. Full writeup:
  [boinc-backend](_docs/knowledge-graph/boinc-backend.md). FAH was never
  attempted. `boinccmd`-not-found and command-failure paths were
  confirmed to fail *gracefully*, which is not the same as confirming the
  real command/parse logic. [fah-backend](_docs/knowledge-graph/fah-backend.md),
  the enforcement half of [scheduling](_docs/knowledge-graph/scheduling.md).
- The dashboard's client-side JS in an actual browser — the metrics
  charts especially, per the `dataviz` skill's own "render it and look at
  it" step, which no amount of API testing substitutes for.
  [metrics](_docs/knowledge-graph/metrics.md), [dashboard-ui](_docs/knowledge-graph/dashboard-ui.md).
- LAN pairing across two genuinely separate machines (this test had
  node and hub on the same host, so mDNS never had to cross a real
  network segment).
- The `dataviz` palette validator script (still no `node` in this
  sandbox).

## Terminology: hub/node -- second rename, not the first

This project has been renamed twice. Both are documented here in order
since later readers need to recognize *both* sets of old terms if they
turn up in old branches, external links, or muscle memory -- not just
the most recent one.

**First rename (2026-08-18): master/agent → manager/worker.** `server/`
→ `manager/`, `client/` → `worker/`, `grid_agent` → `grid_worker`,
`Agent` DB model → `Worker`, `/api/agents` → `/api/workers`, `/ws/agent`
→ `/ws/worker`, `server_url` → `manager_url`, `--server` CLI flag →
`--manager`, `_grid-agent._tcp.local.` mDNS type →
`_grid-worker._tcp.local.`.

**Second rename (2026-08-19): manager/worker → hub/node.** The user felt
"manager"/"worker" read as too corporate for what's meant to be a small,
approachable school/hobbyist tool -- picked from a shortlist (hive/bee,
hub/node, keeper/helper, basecamp/outpost) via preview comparison.
Same full sweep as the first rename: `manager/` → `hub/`, `worker/` →
`node/`, `grid_worker` → `grid_node`, `Worker` DB model → `Node`,
`/api/workers` → `/api/nodes`, `/ws/worker` → `/ws/node`, `manager_url`
→ `hub_url`, `--manager` CLI flag → `--hub`, `_grid-worker._tcp.local.`
mDNS type → `_grid-node._tcp.local.`. Also renamed internally for
clarity, not required by the manager/worker terms themselves: the
WebSocket connection-tracking singleton (`ws_manager.py`'s
`ConnectionManager`/`manager`) → `connections.py`'s
`ConnectionRegistry`/`connections`, since "manager" there was already a
generic "thing that manages connections" name, not a reference to the
hub/manager role -- keeping it named that through the sweep would have
made it read as a stray, unrenamed reference to the old role name.
`node/grid_node/worker.py` (the run-loop module) → `daemon.py`, since
"worker.py" living inside a package already called `grid_node` was
confusing on its own terms, rename or not.

Both renames covered directories, Python identifiers, REST paths, mDNS
service name, config keys, CLI flags, and docs. Neither touched
"client"/"server"/"master"/"worker"/"manager" mentions that refer to
BOINC's or FAHClient's *own* software (e.g. "BOINC client", "FAHClient",
`http.server`/`BaseHTTPRequestHandler`/`httpx.AsyncClient`) or to
generic technical concepts unrelated to our own component roles (e.g.
"WebSocket connection manager" as a pattern name, before it was renamed
to ConnectionRegistry for the unrelated reason above) -- those are
correct, unrelated terminology, not a rename gap.

If you spot a stray "agent", "master", "worker", or "manager" in a
context that clearly means our own hub/node components, it's a rename
gap; grep `\b(agent|master|worker|manager)\b` case-insensitively across
the tree to find it (bare-word matches only -- `worker_id`-style compound
identifiers, and ALL-CAPS ones like `MAX_POINTS_PER_WORKER`, need their
own explicit check since `_` counts as a word character and slips past a
plain `\b` boundary -- confirmed live during the second rename, where
exactly this pattern let a stray `MAX_POINTS_PER_WORKER` constant and a
`GRID_WORKER_CONFIG` env var survive an initial sweep undetected until a
follow-up case-insensitive substring grep with no word boundaries caught
them).
