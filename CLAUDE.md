# GridKeeper — working notes

See [`_docs/REQUIREMENTS.md`](_docs/REQUIREMENTS.md) for the full design
and [`README.md`](README.md) for the quickstart.

## Testing

`hub/tests/` (93 tests: FastAPI `TestClient` + temp SQLite, WebSocket
layer mocked) and `node/tests/` (53 tests: pure logic, all I/O mocked) —
146 total, no CI yet. Run both before trusting a change:

```bash
cd hub && source .venv/bin/activate && pytest tests/ -v
cd node  && source .venv/bin/activate && pytest tests/ -v
```

**When you touch code these tests cover, run them. When you add a new
endpoint or a new piece of non-trivial logic, add a test for it** — with
no CI, "I ran it once by hand" is the only signal until someone runs
`pytest` again, and that signal decays fast. What's covered vs. what
still needs real hardware/a browser: [`_docs/knowledge-graph/testing.md`](_docs/knowledge-graph/testing.md).

## Knowledge graph

[`_docs/knowledge-graph/`](_docs/knowledge-graph/) is a navigation layer over the
codebase: one short markdown file per component/data-model/protocol,
each with a `relates_to` list of the other entities it touches. Start at
`_docs/knowledge-graph/README.md` when orienting in this project cold.
It's a map, not the territory — point into real file paths and
`_docs/REQUIREMENTS.md` for detail rather than restating it. **Keep
entries short** (a paragraph or two): durable facts and current status,
not a day-by-day debugging log — that belongs in git history/commit
messages, not here. Update an entity's `status` the first time something
actually gets runtime-verified; a stale knowledge graph actively
misleads, since it reads as authoritative.

## Terminology: hub/node

This project was renamed twice: `master`/`agent` → `manager`/`worker`
(2026-08-18), then `manager`/`worker` → `hub`/`node` (2026-08-19, since
"manager"/"worker" read as too corporate for a small hobbyist/school
tool). Both sweeps covered directories, Python identifiers, REST paths,
mDNS service name, config keys, CLI flags, and docs — full detail is in
git history if it's ever needed, not reproduced here. Neither rename
touched "client"/"server"/"master"/"worker"/"manager" mentions that
refer to BOINC's/FAHClient's own software or to unrelated generic
technical terms (e.g. "WebSocket connection manager" as a pattern name).

If you spot a stray "agent", "master", "worker", or "manager" referring
to our own hub/node components, it's a rename gap — grep
`\b(agent|master|worker|manager)\b` case-insensitively, and separately
check for compound/ALL-CAPS identifiers (`worker_id`-style, `MAX_POINTS_PER_WORKER`-style)
since `_` counts as a word character and slips past a plain `\b` boundary.
