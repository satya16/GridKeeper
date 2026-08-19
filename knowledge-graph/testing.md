---
id: testing
type: process
status: implemented-verified
files:
  - hub/tests/
  - node/tests/
  - docs/TESTING.md
relates_to: [hub, node]
---

Two automated `pytest` suites (54 tests total, all passing as of
2026-08-11) plus a manual checklist for what they can't cover — full
detail and run instructions in `docs/TESTING.md`, this entry is just the
map pointer.

`hub/tests/` (23 tests) uses FastAPI's `TestClient` against a real
temp-file SQLite DB per test run, with the mDNS discovery registry
stubbed to a no-op (no real network in a unit test) and the WebSocket
`ConnectionRegistry` monkeypatched per-test to simulate an online node
that responds instantly — this exercises [pairing](pairing.md)'s manual
flow, [data-model](data-model.md) persistence, and the hub side of
[wire-protocol](wire-protocol.md)'s command dispatch, all without a real
node process.

`node/tests/` (31 tests) is pure logic with all I/O
(`subprocess`/sockets/`datetime.now()`) monkeypatched: parsing for
[boinc-backend](boinc-backend.md) and [fah-backend](fah-backend.md), and
[scheduling](scheduling.md)'s hour-wrap-past-midnight arithmetic and
idle-detection fail-open behavior — the subtlest, easiest-to-get-wrong
logic in the project, now locked down by tests rather than resting on
having gotten it right by inspection.

Found one real regression while wiring these up (unrelated to test
content): FastAPI's `@app.on_event` is deprecated in the installed
version; `hub/app/main.py` now uses a `lifespan` context hub
instead.

**Not covered, by design** — see `docs/TESTING.md`'s manual checklist:
real `boinccmd`/FAHClient interaction, real mDNS across two machines, and
anything rendered in a browser. Mocking those wouldn't test anything
meaningful; the risk lives entirely in "does the real thing match the
docs," which only the real thing answers.
