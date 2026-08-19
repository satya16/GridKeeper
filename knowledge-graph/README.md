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
  - node/grid_node/schedule.py
  - hub/app/api/schedule.py
relates_to: [hub, node, boinc-backend, fah-backend, wire-protocol]
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
| [hub](hub.md) | component | verified | the FastAPI server app |
| [node](node.md) | component | verified | the per-machine client daemon |
| [pairing](pairing.md) | component | verified | both enrollment flows (manual token, LAN+code) |
| [wire-protocol](wire-protocol.md) | protocol | verified | the WebSocket frame types between node and hub |
| [data-model](data-model.md) | data-model | verified | the SQLite schema (`Node`, `Command`, `PairingToken`) |
| [scheduling](scheduling.md) | component | untested* | hours/idle policy enforcement |
| [metrics](metrics.md) | component | verified | CPU/RAM/temperature collection + live charts |
| [dashboard-ui](dashboard-ui.md) | component | verified | the React + Ant Design web dashboard |
| [boinc-backend](boinc-backend.md) | component | verified‡ | BOINC control via `boinccmd` |
| [fah-backend](fah-backend.md) | component | verified | Folding@home control via its WebSocket API |
| [node-local-ui](node-local-ui.md) | component | untested* | optional per-machine read-only status page, off by default |
| [credentials](credentials.md) | component | verified | saved BOINC account-key repository, single-node apply |
| [testing](testing.md) | process | verified | the automated test suites + manual checklist |

\* partially verified — see the entity for exactly what was and wasn't
exercised. As of 2026-08-11: the wire plumbing works end to end for all
five; what was unverified then was browser-side chart/UI behavior (no
display) and actual BOINC/FAH interaction (neither installed in the test
environment). Both of those are resolved now (browser-side as of
2026-08-18, see [dashboard-ui](dashboard-ui.md); BOINC/FAH interaction
also 2026-08-18, see boinc-backend/fah-backend below) — what's left under
this mark is narrower: [scheduling](scheduling.md)'s enforcement
specifically on BOINC (`apply_schedule()`'s real effect on Activity
behavior was never checked, though the daemon it'd talk to now actually
works) and FAH's enforcement loop reacting to a real schedule boundary
live (the underlying pause/unpause calls it uses are verified, the loop
itself hasn't been watched crossing a boundary).

‡ [boinc-backend](boinc-backend.md)'s long-standing daemon-hang bug is
resolved as of 2026-08-18 (swapped Ubuntu's stale package for BOINC's own
official release build) — status/command path now genuinely verified
live, including a real parsing bug this unblocked finding and fixing
(`run_mode` was silently always "unknown"). Still unverified: attach/detach
and the `Projects`/`Tasks` block-parsing against a *real* attached
project — this machine has no BOINC project account, so that data has
never existed to parse. See the entity for the full story.

## Maintaining this

Add an entity when a new subsystem shows up (a new component, a new
persisted data shape, a new protocol between existing components) — not
for every function or file. When you touch an existing entity's behavior
meaningfully, update its entry rather than letting it drift; a stale
knowledge graph is worse than none, since it's trusted more than a stale
comment would be. `CLAUDE.md` points here for anyone orienting themselves
in the project for the first time.
