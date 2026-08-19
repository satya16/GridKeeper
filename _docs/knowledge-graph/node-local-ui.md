---
id: node-local-ui
type: component
status: implemented-untested
files:
  - node/grid_node/local_ui.py
relates_to: [node, boinc-backend, fah-backend, scheduling, metrics]
---

Optional read-only status page for a single node machine, at
`http://127.0.0.1:<local_ui_port>/` (default 8420) — **off by default**.
Added 2026-08-18 so whoever's sitting at an enrolled lab machine can see
what it's doing, without turning every node into something that
demands attention by default (see [[grid_hub_school_use_case]] in
memory: bulk-enrolled lab PCs should stay unobtrusive unless an admin
opts a machine in).

Toggle with `grid-node local-ui {enable,disable,status}` (writes
`local_ui_enabled`/`local_ui_port` to `config.toml`, same file
[pairing](pairing.md) already manages) — takes effect on next
`grid-node run`.

Deliberately stdlib-only (`http.server.ThreadingHTTPServer` on a daemon
thread), no new dependency, since it runs on every enrolled machine.
Binds to `127.0.0.1` only, never the LAN — enabling it can't expose
anything to other machines on the network. Read-only: no controls here,
pausing/resuming stays a hub-dashboard action
([dashboard-ui](dashboard-ui.md)).

Data flow: `daemon.py::_status_loop` (the same loop that sends status to
the hub over the WebSocket, every `poll_interval_seconds`) also
writes into a `StateBox` — a single dict reference, always replaced
wholesale rather than mutated in place, which is what makes it safe to
read from the HTTP server's own thread without a lock. Page auto-refreshes
every 10s via `<meta http-equiv="refresh">` — no client-side JS at all.
Same escaping discipline as [dashboard-ui](dashboard-ui.md): node
statuses/BOINC project names are node-reported/untrusted, run through
`html.escape()`, never interpolated raw.

**Partially verified (2026-08-18):** `render_page()` and the real
`ThreadingHTTPServer` both covered by `node/tests/test_local_ui.py` (11
tests — including one that starts a real server on an OS-assigned port
and fetches over real HTTP, and an XSS-escaping test). Also manually
smoke-tested end to end on real hardware: started the real server, fed it
this machine's actual `detect_backends()`/`collect_status()`/`metrics.collect()`
output (real BOINC-timeout error, real FAH "no tasks" state, real
CPU/RAM/temperature), fetched over real HTTP, confirmed the rendered HTML
matched expectations. **Not verified: actual rendering in a real
browser** — no browser/display available in this sandbox (same
"no display" gap as [dashboard-ui](dashboard-ui.md) and
[metrics](metrics.md)'s charts) — only the raw HTML/CSS was inspected,
not how a browser actually paints it.
