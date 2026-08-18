# Knowledge graph

A navigation layer over this codebase, not a third copy of its docs. Each
file here is one entity (a component, data model, or protocol) with a
short summary and links to the *other* entities it relates to, plus the
real source of truth: actual file paths, `docs/REQUIREMENTS.md` sections,
and `CLAUDE.md` caveats. The point is that "what does the scheduling
system touch, and what's still unverified about it?" should be answerable
in one file instead of a full-codebase search — useful now, more useful
once this project has too many moving parts to hold in one read-through.

## Format

Each entity is `<id>.md` with YAML frontmatter:

```yaml
---
id: scheduling
type: component            # component | data-model | protocol | process
status: implemented-untested   # see Status values below
files:
  - worker/grid_worker/schedule.py
  - manager/app/api/schedule.py
relates_to: [manager, worker, boinc-backend, fah-backend, wire-protocol]
---
```

followed by a few short paragraphs: what it is, why it's shaped the way
it is (the non-obvious part), and where to look for more (a
`docs/REQUIREMENTS.md` section, a `CLAUDE.md` caveat). Keep entries short
— a paragraph or two plus the links. If an entry is growing past that,
the entity is probably big enough to split, or the detail belongs in
`docs/REQUIREMENTS.md` instead with just a pointer left here.

**`relates_to` is symmetric.** If A relates to B, B lists A back. When you
add an edge, add it on both ends.

### Status values

- `implemented-untested` — written, `py_compile`-clean, never actually
  run.
- `implemented-verified` — either automated-tested (`docs/TESTING.md`'s
  `pytest` suites) or manually confirmed working end to end (dated note
  in the entity, e.g. "Verified 2026-08-11"). Prefer citing which —
  automated coverage stays true; a manual verification note is a
  snapshot that can go stale as the code changes around it.
- `planned` — discussed, not built (e.g. tracked in "Open questions" in
  `docs/REQUIREMENTS.md`).
- `broken` — run against the real thing it targets and confirmed *not*
  to work as written (protocol mismatch, upstream bug, etc.), as opposed
  to `implemented-untested`'s "never actually run." Dated note in the
  entity explains what broke and why.

## Current entities

| id | type | status | what it is |
|---|---|---|---|
| [manager](manager.md) | component | verified | the FastAPI server app |
| [worker](worker.md) | component | verified | the per-machine client daemon |
| [pairing](pairing.md) | component | verified | both enrollment flows (manual token, LAN+code) |
| [wire-protocol](wire-protocol.md) | protocol | verified | the WebSocket frame types between worker and manager |
| [data-model](data-model.md) | data-model | verified | the SQLite schema (`Worker`, `Command`, `PairingToken`) |
| [scheduling](scheduling.md) | component | untested* | hours/idle policy enforcement |
| [metrics](metrics.md) | component | verified | CPU/RAM/temperature collection + live charts |
| [dashboard-ui](dashboard-ui.md) | component | verified | the React + Ant Design web dashboard |
| [boinc-backend](boinc-backend.md) | component | untested* | BOINC control via `boinccmd` |
| [fah-backend](fah-backend.md) | component | verified† | Folding@home control via its WebSocket API |
| [worker-local-ui](worker-local-ui.md) | component | untested* | optional per-machine read-only status page, off by default |
| [testing](testing.md) | process | verified | the automated test suites + manual checklist |

\* partially verified — see the entity for exactly what was and wasn't
exercised. As of 2026-08-11: the wire plumbing works end to end for all
five; what was unverified then was browser-side chart/UI behavior (no
display) and actual BOINC/FAH interaction (neither installed in the test
environment). Browser-side UI is no longer a factor as of 2026-08-18 —
see [dashboard-ui](dashboard-ui.md); what's left under this mark is
narrower: [boinc-backend](boinc-backend.md)'s actual `boinccmd`
interaction (still blocked on a real daemon bug) and
[scheduling](scheduling.md)'s enforcement specifically on BOINC (same
blocker) — FAH's side of both is resolved, see †.

† partially verified differently: as of 2026-08-18, real hardware with a
real FAHClient 8.1.18 daemon confirmed connection, status reporting, and
global pause/unpause end to end (round-tripped through the actual
`worker.py` command-dispatch path). What's still unverified is the
per-work-unit field mapping (`project`/`progress`) against a real,
actively-folding work unit — this machine has no FAH account linked so
never received one. See [fah-backend](fah-backend.md) for the full story,
including a live protocol-version mismatch against the GitHub source.

## Maintaining this

Add an entity when a new subsystem shows up (a new component, a new
persisted data shape, a new protocol between existing components) — not
for every function or file. When you touch an existing entity's behavior
meaningfully, update its entry rather than letting it drift; a stale
knowledge graph is worse than none, since it's trusted more than a stale
comment would be. `CLAUDE.md` points here for anyone orienting themselves
in the project for the first time.
