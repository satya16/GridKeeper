# GridKeeper — working notes

See [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) for the full design,
[`README.md`](README.md) for the quickstart, and
[`docs/TESTING.md`](docs/TESTING.md) for how to test it.

## Testing

There's now a real automated test suite — `manager/tests/` (32 tests:
FastAPI `TestClient` + temp SQLite, WebSocket layer mocked) and
`worker/tests/` (31 tests: pure logic, all I/O mocked) — 63 total. Run
both before trusting a change:

```bash
cd manager && source .venv/bin/activate && pytest tests/ -v
cd worker  && source .venv/bin/activate && pytest tests/ -v
```

**When you touch code these tests cover, run them. When you add a new
endpoint or a new piece of non-trivial logic, add a test for it** — this
project has no CI yet, so "I ran it once by hand" is the only signal
until someone runs `pytest` again, and that signal decays fast. Full
breakdown of what's covered vs. what still needs real hardware/a browser:
`docs/TESTING.md`.

## Knowledge graph

[`knowledge-graph/`](knowledge-graph/) is a navigation layer over the
codebase: one short markdown file per component/data-model/protocol
(manager, worker, pairing, scheduling, metrics, the two backends,
dashboard-ui, data-model, wire-protocol), each with a `relates_to` list
of the other entities it touches. Start there — `knowledge-graph/README.md`
first — when orienting in this project cold, especially once it's grown
past what fits in one read-through of `docs/REQUIREMENTS.md`. It's a
map, not the territory: entries point into real file paths and
`docs/REQUIREMENTS.md`/`CLAUDE.md` for detail rather than restating it.

**Keep it current.** Add an entity when a genuinely new subsystem shows
up; update an existing one when its behavior changes meaningfully
(especially its `status` — see the status vocabulary in
`knowledge-graph/README.md` — the first time something actually gets
runtime-verified, flip it there). A stale knowledge graph actively
misleads, since it reads as authoritative; don't let entries drift from
what `docs/REQUIREMENTS.md` and the code actually say.

## Verified 2026-08-11: core system + LAN pairing work end to end

The `python3.14-venv` sudo blocker is resolved. First real runtime smoke
test happened this session, locally (worker and manager as separate
processes/venvs on the same machine, no BOINC/FAH installed). Confirmed
working: manager boot, auth gate, all REST endpoints, dashboard HTML/JS
serving, both pairing flows (**including the previously-highest-risk
LAN/mDNS discovery path — worked on the first real attempt**), the full
WebSocket wire protocol (status/command/command_result/schedule frames),
worker restart-and-reconnect with no re-enrollment, and schedule-policy
persistence across a reconnect. Per-entity detail and exact verification
notes: [`knowledge-graph/`](knowledge-graph/) (each entity's `status` and
"Verified"/"Partially verified" paragraph) — that's now the authoritative
record of what's confirmed vs. still open, more precise than this file.

One real bug found and fixed by actually running it: `/pair-complete`
didn't send back the manager's *final* chosen worker name (which can
differ from the worker's self-reported one if the admin overrides it
during pairing), so the worker's local `config.toml` could permanently
disagree with the dashboard. Fixed in both `worker/grid_worker/pairing.py`
and `manager/app/api/discovery.py`.

**Still genuinely unverified** (the test environment couldn't exercise
these — see the relevant `knowledge-graph/` entity for specifics):
- Actual BOINC/FAH interaction. BOINC specifically was *attempted* on real
  hardware on 2026-08-13 and hit a real blocker, not just "not installed"
  — Ubuntu's `boinc-client` package has a reproducible, inconsistent GUI
  RPC daemon bug (confirmed across a clean purge+reinstall, AppArmor ruled
  out), and the snap alternative doesn't ship `boinccmd`. Full writeup:
  [boinc-backend](knowledge-graph/boinc-backend.md). FAH was never
  attempted. `boinccmd`-not-found and command-failure paths were
  confirmed to fail *gracefully*, which is not the same as confirming the
  real command/parse logic. [fah-backend](knowledge-graph/fah-backend.md),
  the enforcement half of [scheduling](knowledge-graph/scheduling.md).
- The dashboard's client-side JS in an actual browser — the metrics
  charts especially, per the `dataviz` skill's own "render it and look at
  it" step, which no amount of API testing substitutes for.
  [metrics](knowledge-graph/metrics.md), [dashboard-ui](knowledge-graph/dashboard-ui.md).
- LAN pairing across two genuinely separate machines (this test had
  worker and manager on the same host, so mDNS never had to cross a real
  network segment).
- The `dataviz` palette validator script (still no `node` in this
  sandbox).

## Terminology: manager/worker, not master/agent

The project was renamed throughout (directories, Python identifiers, REST
paths, mDNS service name, config keys, CLI flags, docs) from an earlier
master/agent-based naming: `server/` → `manager/`, `client/` → `worker/`,
`grid_agent` → `grid_worker`, `Agent` DB model → `Worker`, `/api/agents` →
`/api/workers`, `/ws/agent` → `/ws/worker`, `server_url` → `manager_url`,
`--server` CLI flag → `--manager`, `_grid-agent._tcp.local.` mDNS type →
`_grid-worker._tcp.local.`. "Client"/"server" mentions that refer to
BOINC's or FAHClient's *own* client software (e.g. "BOINC client",
"FAHClient", `http.server`/`BaseHTTPRequestHandler`/`httpx.AsyncClient`)
were deliberately left alone -- that's correct, unrelated terminology, not
a rename that was missed. If you spot a stray "agent" or "master" in a
context that clearly means our own components, it's a rename gap; grep
`\bagent\b|\bmaster\b` case-insensitively across the tree to find it
(bare-word matches only -- `agent_id`-style compound identifiers need
their own explicit check since `_` counts as a word character).
