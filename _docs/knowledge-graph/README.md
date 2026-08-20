# Knowledge graph

A navigation layer over this codebase, not a third copy of its docs. Each
file here is one entity (a component, data model, or protocol) with a
short summary and links to the *other* entities it relates to, plus the
real source of truth: actual file paths and `_docs/REQUIREMENTS.md`
sections. The point is that "what does the scheduling system touch, and
what's still unverified about it?" should be answerable in one file
instead of a full-codebase search.

## Format

Each entity is `<id>.md` with YAML frontmatter:

```yaml
---
id: scheduling
type: component            # component | data-model | protocol | process
status: implemented-untested   # see Status values below
files:
  - node/grid_node/schedule.py
  - hub/app/api/schedule.py
relates_to: [hub, node, boinc-backend, fah-backend, wire-protocol]
---
```

followed by a few short paragraphs: what it is, why it's shaped the way
it is (the non-obvious part), and where to look for more. **Keep entries
short — a paragraph or two plus the links.** A dated, blow-by-blow
verification log belongs in git history, not here; if an entry is
growing past that, cut it down to the durable facts (what it does now,
current status) rather than letting it become a session diary.

**`relates_to` is symmetric.** If A relates to B, B lists A back. When you
add an edge, add it on both ends.

### Status values

- `implemented-untested` — written, never actually run.
- `implemented-verified` — automated-tested (`hub/tests/`, `node/tests/`)
  or manually confirmed working end to end (a short dated note in the
  entity, e.g. "Verified 2026-08-19").
- `planned` — discussed, not built (tracked in `_docs/REQUIREMENTS.md`'s
  Open Questions).
- `broken` — run against the real thing it targets and confirmed *not*
  to work as written.

## Current entities

| id | type | status | what it is |
|---|---|---|---|
| [hub](hub.md) | component | verified | the FastAPI server app |
| [node](node.md) | component | verified | the per-machine client daemon |
| [pairing](pairing.md) | component | verified | both enrollment flows (manual token, LAN+code) |
| [wire-protocol](wire-protocol.md) | protocol | verified | the WebSocket frame types between node and hub |
| [data-model](data-model.md) | data-model | verified | the SQLite schema |
| [scheduling](scheduling.md) | component | partial | hours/idle policy enforcement |
| [metrics](metrics.md) | component | verified | CPU/RAM/temperature collection + live charts |
| [dashboard-ui](dashboard-ui.md) | component | verified | the React + Ant Design web dashboard |
| [boinc-backend](boinc-backend.md) | component | verified | BOINC control via `boinccmd` |
| [fah-backend](fah-backend.md) | component | verified | Folding@home control via its WebSocket API |
| [node-local-ui](node-local-ui.md) | component | partial | optional per-machine read-only status page, off by default |
| [credentials](credentials.md) | component | verified | saved BOINC account-key repository |
| [users-and-roles](users-and-roles.md) | component | verified | multi-user accounts, four-tier RBAC, audit log |
| [testing](testing.md) | process | verified | the automated test suites |

`scheduling`'s remaining gap: `apply_schedule()`'s real effect on BOINC's
Activity behavior, and FAH's enforcement loop crossing a real hours/idle
boundary live, are both unverified (the underlying suspend/pause calls
they use are verified). `node-local-ui`'s gap: never actually painted by
a real browser, only fetched over raw HTTP.

## Maintaining this

Add an entity when a new subsystem shows up — not for every function or
file. When you touch an existing entity's behavior meaningfully, update
its entry rather than letting it drift; a stale knowledge graph is worse
than none, since it's trusted more than a stale comment would be.
`CLAUDE.md` points here for anyone orienting themselves in the project
for the first time.
