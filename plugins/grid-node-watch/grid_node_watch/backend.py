"""Generic process-watcher grid_node.backends plugin: point it at any
program by name via a config file, no per-program plugin needed (contrast
grid_node_gimps.backend, which is hand-written for one specific client).

Live-verified 2026-08-24 end-to-end on a real hub+node pair (scratch hub
on a spare port/DB, node enrolled with a scratch config so the real
dev-machine node setup was untouched): a real ffmpeg process (1080p
libx264 encode, not a toy sleep loop) started via a hub-issued command,
found and reported on across several real status polls with cpu_percent
tracking real multi-core load (~650%, matching `ps` independently),
uptime increasing correctly between polls, then stopped cleanly via a
second hub command -- confirmed both by the hub's own status view and by
checking the OS process directly. `/api/backends` was confirmed to
report this backend's label/actions correctly, which is what the
dashboard's GenericBackendBlock.jsx fallback UI renders from.

That session also *found and fixed* a real bug: the first version of
_find_process() matched `match` against the entire command line, which
falsely matched this plugin's own test harness (a `bash -c` process whose
argument text happened to contain the target name as data, not as the
running program) as "already running." See _find_process()'s docstring
for the fix and its own remaining known gap.

Config: a JSON file (default ~/.local/share/grid-node-watch/targets.json,
override with GRIDKEEPER_WATCH_CONFIG) listing one or more targets:

    {
      "targets": [
        {"name": "blender-render", "match": "blender",
         "start_cmd": ["/usr/bin/blender", "-b", "render.blend"],
         "stop_signal": "SIGTERM"},
        {"name": "matlab", "match": "MATLAB"}
      ]
    }

"name" is the id used in ACTIONS payloads and as the get_status() dict key
-- arbitrary, chosen by whoever writes the config. "match" is a
case-insensitive substring matched against each running process's name
plus its full command line (so "blender" matches a process named
"blender" *or* one invoked as "/opt/foo/blender-bin --headless"). A target
with no "start_cmd" is watch-only: get_status() still reports it, but
start() refuses it -- same "can't safely automate what we don't control"
boundary grid_node_gimps.backend draws around mprime's first-run wizard,
here applied to "we don't know how you'd launch this."

Unlike BOINC/FAH/GIMPS, there's no single well-known program this targets
-- so unlike those modules, this one is deliberately configured rather
than auto-detected. is_available() is true as soon as at least one target
is configured, regardless of whether that program happens to be running
right now (matching boinc.py/fah.py's "is the client installed", not "is
it currently active" -- get_status()'s per-target "running" is where
current activity shows up).
"""

import json
import logging
import os
import signal
import subprocess
import threading
import time

import psutil

logger = logging.getLogger("grid_node_watch")

NAME = "watch"
LABEL = "Watched Processes"

# No SENSITIVE_FIELDS: start/stop payloads only ever carry a target name,
# never a credential. No CREDENTIAL_ACTION: there's no account/service
# this backend authenticates to -- it only watches/launches local
# processes, same boundary grid_node_gimps.backend draws for the same
# reason.

_DEFAULT_DIR = os.path.expanduser("~/.local/share/grid-node-watch")
_OWN_PID = os.getpid()


class WatchError(RuntimeError):
    pass


def _watch_dir() -> str:
    return os.environ.get("GRIDKEEPER_WATCH_DIR", _DEFAULT_DIR)


def _config_path() -> str:
    return os.environ.get("GRIDKEEPER_WATCH_CONFIG", os.path.join(_watch_dir(), "targets.json"))


def _load_targets() -> list[dict]:
    """Read fresh from disk every call (no caching), same convention as
    grid_node_gimps.backend._binary() -- lets an admin edit the config
    without restarting grid-node for it to notice. Missing/unreadable/
    malformed config fails open to an empty list rather than raising, same
    fail-open style boinc.py/fah.py use for anything install-state
    dependent -- a bad config should make this backend report nothing to
    watch, not crash the node's whole status loop."""
    try:
        with open(_config_path()) as f:
            data = json.load(f)
        targets = data.get("targets", [])
        if not isinstance(targets, list):
            raise ValueError("'targets' must be a list")
        return targets
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("grid-node-watch config at %s is invalid, ignoring: %s", _config_path(), e)
        return []


def _target_by_name(name: str) -> dict:
    for target in _load_targets():
        if target.get("name") == name:
            return target
    raise WatchError(f"no watch target named '{name}' in {_config_path()}")


def is_available() -> bool:
    return bool(_load_targets())


_INTERPRETER_BASENAMES = {"bash", "sh", "zsh", "dash", "perl", "ruby", "node", "nodejs"}


def _is_interpreter(basename: str) -> bool:
    # startswith, not ==, to cover version-suffixed binaries (python3,
    # python3.11) without an ever-growing exact-name list.
    return basename in _INTERPRETER_BASENAMES or basename.startswith("python")


def _find_process(match: str) -> psutil.Process | None:
    """First running process (other than this node process itself) whose
    *executable identity* contains `match`, case-insensitively -- psutil's
    `.name()`, the basename of argv[0] (covers a wrapper/absolute-path
    invocation like "/opt/blender-3.6/blender-bin"), and, when argv[0] is
    a known script interpreter, the basename of argv[1] too (covers a
    shebang script exec'd directly, e.g. "./fake-watch-target.sh" --
    the kernel rewrites its argv to ["/bin/bash", "/path/to/script.sh",
    ...], so the script's own name lands in argv[1], not argv[0] or
    `.name()`, which report "bash").

    Found live 2026-08-24: an earlier version matched `match` against the
    *entire* command line. On a real dev machine running other things,
    that matched this very plugin's own test harness -- a
    `bash -c '<a python one-liner containing the word "ffmpeg" as a
    string literal>'` process -- purely because the word appeared as data
    inside one argument, nowhere near identifying the program actually
    running. Deliberately not scanning every argument for `match` (as
    opposed to just argv[0]/argv[1]'s basename) is what avoids that class
    of false positive; the tradeoff is a target invoked as `python3 -m
    mymodule` or with the real name past argv[1] won't be found this way
    -- a known gap, not attempted here."""
    needle = match.lower()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        if proc.info["pid"] == _OWN_PID:
            continue
        try:
            name = proc.info.get("name") or ""
            cmdline = proc.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        candidates = [name]
        if cmdline:
            argv0_base = os.path.basename(cmdline[0])
            candidates.append(argv0_base)
            if _is_interpreter(argv0_base) and len(cmdline) > 1:
                candidates.append(os.path.basename(cmdline[1]))
        haystack = " ".join(candidates).lower()
        if needle in haystack:
            return proc
    return None


def _process_status(proc: psutil.Process) -> dict:
    try:
        with proc.oneshot():
            cmdline = proc.cmdline()
            create_time = proc.create_time()
            # cpu_percent(interval=None) is non-blocking but reports 0.0 on
            # the *first* call for a given psutil.Process object, since
            # it's comparing against no prior baseline -- a documented
            # psutil quirk, not a bug here. It becomes meaningful on the
            # next status poll for the same underlying process. A future
            # pass could cache Process objects across polls to avoid this;
            # left as a known gap rather than added speculatively.
            cpu_percent = proc.cpu_percent(interval=None)
            mem_percent = proc.memory_percent()
        return {
            "running": True,
            "pid": proc.pid,
            "cpu_percent": cpu_percent,
            "mem_percent": round(mem_percent, 2),
            "uptime_seconds": round(time.time() - create_time, 1),
            "cmdline": cmdline,
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        # Process exited between _find_process() finding it and us reading
        # its info, or we don't have permission to read another user's
        # process details -- either way, honest "not running" beats a
        # crashed status loop.
        return {"running": False, "error": str(e)}


def get_status() -> dict:
    status = {}
    for target in _load_targets():
        name = target.get("name")
        match = target.get("match")
        if not name or not match:
            continue
        proc = _find_process(match)
        entry = _process_status(proc) if proc is not None else {"running": False, "pid": None}
        entry["has_start_cmd"] = bool(target.get("start_cmd"))
        status[name] = entry
    return status


def _reap(proc: subprocess.Popen) -> None:
    """Background wait() so a target that exits quickly after start()
    (misconfigured command, crashes on launch, etc.) doesn't sit as a
    zombie under grid-node's pid -- same fix grid_node_gimps.backend.start()
    needed after finding that exact failure mode live against real mprime."""
    proc.wait()


def start(payload: dict) -> dict:
    name = (payload or {}).get("target")
    if not name:
        raise WatchError("payload must include 'target' (the target's configured name)")
    target = _target_by_name(name)

    existing = _find_process(target["match"])
    if existing is not None:
        return {"already_running": True, "pid": existing.pid}

    start_cmd = target.get("start_cmd")
    if not start_cmd:
        raise WatchError(f"target '{name}' has no start_cmd configured -- watch-only, start it yourself")

    os.makedirs(_watch_dir(), exist_ok=True)
    log_path = os.path.join(_watch_dir(), f"{name}.log")
    with open(log_path, "ab") as log_file:
        # start_new_session so it survives grid-node's own process
        # lifecycle, same reasoning as grid_node_gimps.backend.start().
        proc = subprocess.Popen(
            start_cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    threading.Thread(target=_reap, args=(proc,), daemon=True).start()
    return {"started": True, "pid": proc.pid}


def stop(payload: dict) -> dict:
    name = (payload or {}).get("target")
    if not name:
        raise WatchError("payload must include 'target' (the target's configured name)")
    target = _target_by_name(name)

    proc = _find_process(target["match"])
    if proc is None:
        return {"already_stopped": True}

    sig_name = target.get("stop_signal", "SIGTERM")
    sig = getattr(signal, sig_name, None)
    if sig is None:
        raise WatchError(f"target '{name}' has invalid stop_signal '{sig_name}'")
    os.kill(proc.pid, sig)
    return {"stopping": True, "pid": proc.pid}


ACTIONS = {
    "start": start,
    "stop": stop,
}
