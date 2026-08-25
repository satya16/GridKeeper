---
id: plugin-registry
type: component
status: implemented-verified
files:
  - node/grid_node/backends/base.py
  - node/grid_node/backends/__init__.py
  - node/pyproject.toml
  - hub/app/api/backends.py
  - hub/app/db.py
relates_to: [node, hub, boinc-backend, fah-backend, gimps-backend, credentials, dashboard-ui]
---

Makes backends (BOINC/FAH, and anything else) a real plugin system instead
of two hardcoded modules: a third party can `pip install` a separate
package that adds a new distributed-computing backend with **zero edits**
to `grid-node`/GridKeeper's own source. Two halves:

**Node side** (`backends/base.py`, `backends/__init__.py`): a backend is a
plain module (matches `boinc.py`/`fah.py`'s existing function-module
style, no class hierarchy) registered under the `grid_node.backends`
entry-point group. `discover_backends()` uses
`importlib.metadata.entry_points(group="grid_node.backends")` and
validates each via `base.validate_backend()` (clear error + skip, not a
crash, if a plugin is missing required attributes). boinc.py/fah.py
register themselves under this *same* mechanism (`node/pyproject.toml`) --
no special-cased "built-in" path, so they exercise exactly what a third
party does. Required: `NAME`, `LABEL`, `is_available()`, `get_status()`,
`ACTIONS`. Optional: `SENSITIVE_FIELDS`, `CREDENTIAL_ACTION`,
`apply_schedule()` (only if the backend has its own native idle/hours
engine like BOINC -- `daemon.py::_apply_native_schedules` now dispatches
to *any* backend declaring one, not just a hardcoded "boinc" check).

**Hub side**: the hub can't import a node's Python (separate deployables,
often separate machines), so it *learns* a backend's shape from the wire.
Every status frame now carries a `capabilities` block
(`daemon.py::collect_capabilities`, built from `backends/base.py::capabilities()`)
that `main.py::node_ws` upserts into a `BackendCapability` table
(`GET /api/backends`) -- independent of any one node, since a credential
needs to be creatable before a matching node happens to be online. This
replaced two things that used to be hardcoded in `hub/app/api/nodes.py`:
the `_SENSITIVE_PAYLOAD_FIELDS` redaction dict (now looked up from the
registry) and `CommandRequest.backend`'s `Literal["boinc", "fah"]` (now
plain `str`). See [credentials](credentials.md) for how the saved-
credential repository was generalized the same way.

Dashboard: known backends (boinc/fah) keep their dedicated
`BoincBlock`/`FahBlock` React components; anything else renders via
`GenericBackendBlock.jsx` (raw status JSON + an action picker built from
the registry's `actions` list) -- less polished, but usable immediately
for a plugin the dashboard's own code has never heard of. See
[dashboard-ui](dashboard-ui.md).

**Verified**: real end-to-end proof via [gimps-backend](gimps-backend.md)
-- a genuinely separate installable package (`plugins/grid-node-gimps/`)
picked up by `discover_backends()` with no `grid-node` source changes,
its capabilities correctly populated `GET /api/backends` from a live
status frame, and a `start` command dispatched through the full stack
(dashboard/REST -> WebSocket -> node -> plugin -> a real OS process).
`boinc`/`fah` themselves re-verified unchanged after this refactor
(attach/suspend/resume against real BOINC, pause/unpause against real
FAH, redaction still correct) -- see their own entries.
