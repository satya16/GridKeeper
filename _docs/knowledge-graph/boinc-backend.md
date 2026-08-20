---
id: boinc-backend
type: component
status: implemented-verified
files:
  - node/grid_node/backends/boinc.py
relates_to: [node, scheduling, credentials]
---

Controls a locally-installed BOINC client by shelling out to `boinccmd`
rather than speaking the GUI RPC protocol on port 31416 directly —
trades some parsing fragility (text-output scraping) for not needing
RPC's auth handshake. `get_status()` parses `boinccmd
--get_simple_gui_info`/`--get_cc_status`; commands (`suspend_project`,
`resume_project`, `suspend_all`, `resume_all`, `attach_project`,
`detach_project`) map to the matching `boinccmd` flags.

`attach_project(url, account_key)` takes the project's long-lived
account authenticator. The hub (`hub/app/api/nodes.py::_redact_payload`)
masks `account_key` before persisting a command to the audit-log table
or echoing it back from the API — the real key still reaches the node
over the WebSocket, only what's stored/returned is redacted. New
sensitive payload fields go in `_SENSITIVE_PAYLOAD_FIELDS` there.

`apply_schedule()` (used by [scheduling](scheduling.md)) writes a temp
`global_prefs_override.xml` via `boinccmd --set_global_prefs_override` +
`--read_global_prefs_override`, letting BOINC's own idle/hours engine
enforce it rather than polling from the node side.

`attach_project()` also checks `get_status()`'s current project list
itself before calling `boinccmd`, since BOINC's own "already attached"
rejection isn't reliable against a rapid repeat call (confirmed live: a
double-click briefly created real duplicate project entries). **Known
residual gap**: the guard compares the literal `project_url` string;
once BOINC resolves a project's master file the reported URL can flip to
a different domain, which a spaced-out repeat attach could still slip
past. Closing this fully would mean replicating BOINC's own URL
resolution or tracking attach/detach history server-side — not done, the
current guard already closes the realistic trigger (rapid/accidental
double-submit).

**Verified live** against a real BOINC install (BOINC's own official
`.deb` release, not Ubuntu's stale/buggy package — see git history if
that swap ever needs repeating) and a real Einstein@Home account:
`suspend_all`/`resume_all`/`attach_project` all confirmed changing real
daemon state, round-tripped through the actual WebSocket dispatch path.
Two real parsing bugs found and fixed this way (wrong `run_mode` field
name; nested `GUI URL:` sub-entries clobbering the project name) — both
now covered by `node/tests/test_boinc.py` fixtures captured from live
output. `cpu_suspend_reason` (e.g. "on batteries") also added and
verified. Still unverified: `detach_project` against a real project (left
attached deliberately for future testing), and the dashboard's React
rendering of this data isn't independently browser-verified beyond the
API response shape.
