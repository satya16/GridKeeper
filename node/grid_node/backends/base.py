"""The backend plugin interface. A backend is a plain module (not a class --
matches boinc.py/fah.py's existing style) registered under the
`grid_node.backends` entry-point group (see backends/__init__.py). This file
documents the contract via a Protocol for type-checking/reference; nothing
here is imported at runtime by boinc.py/fah.py themselves.

Required:
  NAME: str                          -- matches the entry-point name
  LABEL: str                         -- human-readable, shown in the dashboard
  is_available() -> bool             -- can this backend's client be controlled here?
  get_status() -> dict                -- arbitrary JSON-serializable status
  ACTIONS: dict[str, Callable[[dict], dict]]  -- action name -> handler(payload)

Optional:
  SENSITIVE_FIELDS: dict[str, set[str]]   -- action -> payload keys that are
    long-lived credentials, never persisted/echoed in plaintext by the hub
    (see hub/app/api/nodes.py::_redact_payload). Defaults to {} (nothing
    sensitive) if absent.
  CREDENTIAL_ACTION: dict | None     -- {"action": str, "key_field": str,
    "static_fields": list[str]} if this backend supports the hub's saved-
    credential repository (see hub/app/api/credentials.py); None/absent if
    it doesn't (e.g. fah.py has none).
  apply_schedule(policy: dict) -> dict  -- present only if this backend has
    its own native idle/hours engine (see boinc.py); backends without one
    are enforced by the node's generic schedule loop instead (see
    node/grid_node/schedule.py and daemon.py::_fah_schedule_loop for the
    FAH precedent a third backend without native scheduling should follow).
"""

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class BackendModule(Protocol):
    NAME: str
    LABEL: str
    ACTIONS: dict[str, Callable[[dict], dict]]

    def is_available(self) -> bool: ...
    def get_status(self) -> dict[str, Any]: ...


_REQUIRED_ATTRS = ("NAME", "LABEL", "is_available", "get_status", "ACTIONS")


class InvalidBackend(RuntimeError):
    pass


def validate_backend(module: Any) -> None:
    """Raises InvalidBackend with a specific, actionable message if `module`
    doesn't implement the required surface -- called at registry-load time
    (backends/__init__.py::discover_backends) so a broken third-party plugin
    fails loudly at node startup rather than with a confusing AttributeError
    the first time a status poll or command happens to touch the missing
    piece."""
    missing = [attr for attr in _REQUIRED_ATTRS if not hasattr(module, attr)]
    if missing:
        raise InvalidBackend(
            f"backend module '{getattr(module, '__name__', module)}' is missing required "
            f"attribute(s): {', '.join(missing)} -- see grid_node.backends.base for the interface"
        )
    if not isinstance(module.ACTIONS, dict):
        raise InvalidBackend(f"backend '{module.NAME}': ACTIONS must be a dict, got {type(module.ACTIONS)}")


def capabilities(module: Any) -> dict[str, Any]:
    """The subset of a backend's declared shape the hub needs but can't
    import Python code to get (hub and node are separate deployables, often
    on different machines) -- sent over the wire in each status frame's
    `capabilities` block. See daemon.py::_status_loop."""
    return {
        "label": getattr(module, "LABEL", module.NAME),
        "sensitive_fields": {
            action: sorted(fields) for action, fields in getattr(module, "SENSITIVE_FIELDS", {}).items()
        },
        "credential_action": getattr(module, "CREDENTIAL_ACTION", None),
        "actions": sorted(module.ACTIONS.keys()),
    }
