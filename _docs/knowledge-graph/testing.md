---
id: testing
type: process
status: implemented-verified
files:
  - hub/tests/
  - node/tests/
relates_to: [hub, node]
---

Two automated `pytest` suites — run instructions in `CLAUDE.md` (which
has the current counts; not duplicated here to avoid the two drifting
apart).

`hub/tests/` uses FastAPI's `TestClient` against a real temp-file SQLite
DB, with mDNS stubbed to a no-op and the WebSocket `ConnectionRegistry`
monkeypatched to simulate an online node. Covers auth/RBAC, both
enrollment flows, node/credential/schedule CRUD and scope-permission
boundaries, and command dispatch.

`node/tests/` is pure logic with all I/O
(`subprocess`/sockets/`datetime.now()`) monkeypatched: BOINC/FAH output
parsing against captured real responses, and
[scheduling](scheduling.md)'s hour-wrap-past-midnight arithmetic and
idle-detection fail-open behavior.

**Not covered, by design**: real `boinccmd`/FAHClient interaction (these
have instead been verified manually against real installs — see
[boinc-backend](boinc-backend.md)/[fah-backend](fah-backend.md)), real
mDNS across two separate machines, and anything requiring an actual
browser paint (frontend has its own separate Playwright smoke test, see
[dashboard-ui](dashboard-ui.md)).
