"""Controls a locally-running FAHClient (v8, "Bastet") via its local JSON
WebSocket API at ws://127.0.0.1:7396/api/websocket -- the only control
surface the client exposes (confirmed against the fah-client-bastet
source: Server.cpp registers exactly one real endpoint, GET
/api/websocket; everything else 404s or redirects to the web-control UI).
FAHClient v7's plain-text PyON protocol on port 36330, which this module
used to speak, doesn't exist in this client at all.

On connect the server immediately pushes one full-state message -- a JSON
dict -- before anything else (see Remote::onOpen in the client source: it
unconditionally sends the whole App object first). Every call here opens
a short-lived connection and reads just that first message, mirroring
the old module's one-shot-connection-per-command style rather than
keeping a long-lived connection and tracking the incremental diffs the
server streams after it.

The upstream GitHub source (FoldingAtHome/fah-client-bastet, `master`)
describes a richer protocol than what 8.1.18 -- the version actually
distributed by foldingathome.org as of 2026-08-18 -- speaks: `master`
has a `{"cmd": "state", "state": ..., "group": ...}` message and a
top-level "groups" dict for per-resource-group control. Live-tested
against a real 8.1.18 daemon, that form is silently ignored (no error,
no state change). What actually works, confirmed via the delta message
it produces (`["config", "paused", true]`): the plain deprecated-in-source
`{"cmd": "pause"}` / `{"cmd": "unpause"}`, which are global -- there is no
"groups" key in this version's wire format at all, so there is no
per-slot targeting to do. Every work unit's own "group" field is always
"" in practice. pause_slot/unpause_slot below accept a slot_id for API
-shape compatibility but act globally, same as pause_all/unpause_all --
there is currently nothing narrower to target.
"""

import json

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

FAH_HOST = "127.0.0.1"
FAH_PORT = 7396
FAH_WS_URL = f"ws://{FAH_HOST}:{FAH_PORT}/api/websocket"


class FahError(RuntimeError):
    pass


def is_available(url: str = FAH_WS_URL) -> bool:
    try:
        with connect(url, open_timeout=2.0, close_timeout=1.0):
            return True
    except (OSError, WebSocketException):
        return False


def _get_state(url: str = FAH_WS_URL, timeout: float = 5.0) -> dict:
    try:
        with connect(url, open_timeout=timeout, close_timeout=1.0) as ws:
            raw = ws.recv(timeout=timeout)
    except (OSError, WebSocketException, TimeoutError) as e:
        raise FahError(f"could not reach FAHClient at {url}: {e}") from e

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise FahError(f"could not parse FAHClient state: {e}") from e


def _send_command(payload: dict, url: str = FAH_WS_URL, timeout: float = 5.0) -> None:
    try:
        with connect(url, open_timeout=timeout, close_timeout=1.0) as ws:
            ws.send(json.dumps(payload))
    except (OSError, WebSocketException, TimeoutError) as e:
        raise FahError(f"could not reach FAHClient at {url}: {e}") from e


def get_status() -> dict:
    """Returns {"slots": [...], "account": {"user", "team", "cause", "fold_anon"}}.

    The project number lives at unit["assignment"]["project"] -- confirmed
    2026-08-18 against a real assigned work unit (project 18292). Originally
    guessed as unit["wu"]["project"] from reading the upstream source, which
    was wrong: "wu" actually holds run/clone/gen/collection-server fields,
    no project number at all. Left as a cautionary example in the module
    history (see _docs/knowledge-graph/fah-backend.md) of why this client's wire
    format needs verifying live, not just read from source.

    "account" deliberately excludes "passkey" -- this flows into the
    hub's node-status table (overwritten each poll, but still
    persisted), unlike the one-shot command payload set_config() takes,
    so it gets the same "never echo a credential back" treatment as
    hub/app/api/nodes.py's command-payload redaction.
    """
    state = _get_state()
    units = state.get("units") or {}
    if isinstance(units, dict):
        units = units.values()

    slots = []
    for unit in units:
        assignment = unit.get("assignment") or {}
        project = assignment.get("project")
        slots.append(
            {
                "id": unit.get("group", ""),
                "status": unit.get("state", "unknown"),
                "project": str(project) if project is not None else None,
                "progress": unit.get("progress", 0.0),
            }
        )

    config = state.get("config") or {}
    account = {
        "user": config.get("user", "Anonymous"),
        "team": config.get("team", 0),
        "cause": config.get("cause", "any"),
        "fold_anon": config.get("fold_anon", False),
    }
    return {"slots": slots, "account": account}


def pause_all() -> dict:
    _send_command({"cmd": "pause"})
    return {"paused": "all"}


def unpause_all() -> dict:
    _send_command({"cmd": "unpause"})
    return {"paused": "none"}


def pause_slot(slot_id: str) -> dict:
    _send_command({"cmd": "pause"})
    return {"slot_id": slot_id, "paused": True}


def unpause_slot(slot_id: str) -> dict:
    _send_command({"cmd": "unpause"})
    return {"slot_id": slot_id, "paused": False}


_CONFIGURABLE_FIELDS = {"user", "team", "passkey", "fold_anon", "cause"}


def set_config(fields: dict) -> dict:
    """Live-verified 2026-08-18 against a real 8.1.18 daemon: unlike the
    "state" cmd (dead in this shipped version -- see module docstring),
    {"cmd": "config", "config": {...}} is honored, confirmed via the
    resulting delta pushes (e.g. ["config", "cause", "cancer"]) and via a
    fresh connection's config afterward. Setting fold_anon=true with no
    linked account actually got a real work unit assigned within a
    second -- so this genuinely starts real folding, not just a config
    write. Only whitelisted fields are ever passed through -- the FAH
    config object has other keys (cpus, gpus, on_idle, beta, ...) this
    module doesn't manage."""
    unknown = set(fields) - _CONFIGURABLE_FIELDS
    if unknown:
        raise FahError(f"unsupported config field(s): {', '.join(sorted(unknown))}")
    _send_command({"cmd": "config", "config": fields})
    return {"updated": sorted(fields)}


ACTIONS = {
    "pause_all": lambda payload: pause_all(),
    "unpause_all": lambda payload: unpause_all(),
    "pause_slot": lambda payload: pause_slot(payload["slot_id"]),
    "unpause_slot": lambda payload: unpause_slot(payload["slot_id"]),
    "set_config": lambda payload: set_config(payload),
}
