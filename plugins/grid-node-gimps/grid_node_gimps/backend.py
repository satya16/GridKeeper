"""Controls a locally-installed mprime (the GIMPS/Great Internet Mersenne
Prime Search command-line client) -- proof-of-concept third-party
grid_node.backends plugin, packaged and registered exactly the way an
unrelated developer would (see this package's pyproject.toml entry point),
not a special-cased "built-in" like boinc.py/fah.py.

Real binary confirmed live 2026-08-24: downloaded and checksum-verified
mprime 30.19 build 20 from download.mersenne.ca (the official GIMPS
mirror), drove its interactive first-run wizard (Join Gimps? -> N for
"just stress testing", which needs no PrimeNet account -- matches this
backend having no CREDENTIAL_ACTION, same boundary fah.py already has for
a different reason) through to a genuinely running torture-test worker
(real Lucas-Lehmer iterations on a real Mersenne candidate, confirmed via
`ps` showing real sustained CPU use), then stopped it with SIGINT and
confirmed a clean exit -- no orphaned process, mprime.pid removed on its
own. That live session is also where the config file (prime.txt) and pid
file (mprime.pid) mechanics below come from -- both directly observed, not
guessed from documentation alone. The full interactive wizard automation
used to reach that state (see the project's session history) is a *testing*
technique, not something this module does at runtime: start() below
deliberately does NOT try to answer mprime's setup prompts on someone's
real machine, and errors clearly if that one-time setup hasn't been done
yet by a human.

Unlike BOINC/FAH, mprime has no live control RPC/socket to speak to a
process that's already running -- confirmed live: a second `mprime -s`
invocation while a torture test was running didn't return a lightweight
status snapshot, it launched an entire second interactive instance. So
the only real remote-controllable primitives here are starting/stopping
the worker process itself (matching this project's "honest scope" design
choice, see _docs/knowledge-graph/gimps-backend.md) -- not a missing
feature, a real limitation of the underlying tool.

**Known gap, found live, not yet closed**: the session above set up
mprime's *torture test* mode (`StressTester=1` in prime.txt) -- a CPU/
memory stress diagnostic, not actual Mersenne-prime search work. A bare
relaunch (`mprime -d`, what start() does) does not resume a torture test
on its own -- it lands back at mprime's interactive Main Menu waiting for
a menu choice, and with stdin closed (start() uses DEVNULL, deliberately,
so it can't block on or accidentally answer a real prompt) it exits
almost immediately. Confirmed live: this left a zombie process under
grid-node until a reaper thread was added (see start() below). What's
*expected* to work unattended -- prime95/mprime's actual PrimeNet work
mode (`UsePrimenet=1`, or manual worktodo.txt entries), which the readme
describes as running continuously once configured, unlike torture test --
was not itself live-verified in this session. Until that's confirmed,
treat start()/stop() as verified for "launch/stop the mprime process
cleanly," not for "correctly resume real search work across a restart."
"""

import os
import signal
import subprocess
import threading

NAME = "gimps"
LABEL = "GIMPS (mprime)"

# No SENSITIVE_FIELDS: start/stop take no credential-shaped payload.
# No CREDENTIAL_ACTION: PrimeNet account linking (if ever wanted) is a
# manual one-time `mprime -m` step, same boundary fah.py draws for its
# passkey -- see node/grid_node/backends/fah.py.

_DEFAULT_DIR = os.path.expanduser("~/.local/share/grid-node-gimps")


class GimpsError(RuntimeError):
    pass


def _work_dir() -> str:
    return os.environ.get("GRIDKEEPER_GIMPS_DIR", _DEFAULT_DIR)


def _binary() -> str | None:
    """Read fresh from the environment each call (no caching), same
    convention as hub/app/crypto.py's SECRET_KEY_ENV -- lets an admin
    change/uninstall mprime without restarting grid-node for it to notice."""
    configured = os.environ.get("GRIDKEEPER_GIMPS_BIN")
    if configured:
        return configured if os.path.isfile(configured) else None
    for candidate in ("mprime", "prime95"):
        found = _which(candidate)
        if found:
            return found
    return None


def _which(name: str) -> str | None:
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(path_dir, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_available() -> bool:
    return _binary() is not None


def _pid_file() -> str:
    return os.path.join(_work_dir(), "mprime.pid")


def _read_pid() -> int | None:
    try:
        with open(_pid_file()) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just owned by someone else -- still "alive"
    return True


def _tail_log_line() -> str | None:
    """Best-effort last line of prime.log, for a human-readable "what's it
    doing right now" -- confirmed live that mprime writes worker-activity
    lines here (e.g. "Test 1, 4800 Lucas-Lehmer iterations of M53477377
    ..."). Missing/unreadable file is not an error, same fail-open style
    boinc.py/fah.py use for anything platform/install-state dependent."""
    path = os.path.join(_work_dir(), "prime.log")
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 4096))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        return lines[-1] if lines else None
    except FileNotFoundError:
        return None


def get_status() -> dict:
    """Returns {"running": bool, "pid": int|None, "work_dir": str,
    "configured": bool, "last_log_line": str|None}.

    "configured" is False if prime.txt (written by mprime's own first-run
    wizard) doesn't exist yet in the work dir -- distinguishes "installed
    but never set up" from "set up but currently stopped", since start()
    below refuses to run in the former case.

    Deliberately does NOT attempt to parse results.json.txt for recent
    PRP/LL results -- readme.txt documents that file's existence but this
    was only ever live-tested in torture-test mode, which doesn't produce
    it (no PrimeNet work assigned), so a parser here would be untested
    guesswork. Left for a future pass once verified against real primality-
    test output -- see _docs/knowledge-graph/gimps-backend.md.
    """
    pid = _read_pid()
    running = pid is not None and _pid_alive(pid)
    return {
        "running": running,
        "pid": pid if running else None,
        "work_dir": _work_dir(),
        "configured": os.path.isfile(os.path.join(_work_dir(), "prime.txt")),
        "last_log_line": _tail_log_line(),
    }


def start(payload: dict | None = None) -> dict:
    status = get_status()
    if status["running"]:
        return {"already_running": True, "pid": status["pid"]}
    if not status["configured"]:
        raise GimpsError(
            f"mprime has never been set up in {status['work_dir']} -- run `mprime -m` there once by hand "
            "(interactive: license terms, PrimeNet-or-manual choice, resource limits) before grid-node can start it"
        )
    binary = _binary()
    if binary is None:
        raise GimpsError("mprime/prime95 not found on PATH or GRIDKEEPER_GIMPS_BIN")

    work_dir = status["work_dir"]
    log_path = os.path.join(work_dir, "grid-node-gimps.out.log")
    with open(log_path, "ab") as log_file:
        # start_new_session so it survives grid-node's own process
        # lifecycle (same reason BOINC/FAH clients run as their own
        # separate daemons rather than children of grid-node) -- confirmed
        # live that a graceful SIGINT (stop() below) is what actually
        # tears it down cleanly, not process-group signals from a parent.
        proc = subprocess.Popen(
            [binary, "-d"],
            cwd=work_dir,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    # Found live: with nothing reaping it, an mprime that exits quickly
    # (e.g. relaunched with no stdin while sitting at its interactive Main
    # Menu rather than actively working -- see the module docstring's
    # "what start() does and doesn't resume" note) becomes a zombie under
    # grid-node's pid, and stays one for as long as grid-node keeps
    # running. A daemon thread just to reap it is the minimal fix that
    # doesn't block start()'s own return.
    threading.Thread(target=proc.wait, daemon=True).start()
    return {"started": True}


def stop(payload: dict | None = None) -> dict:
    status = get_status()
    if not status["running"]:
        return {"already_stopped": True}
    # SIGINT, not SIGTERM/SIGKILL -- confirmed live this is what mprime's
    # own readme means by "safely interrupted... writes intermediate
    # results to disk" (the ESC-key behavior in its interactive UI maps to
    # SIGINT for a backgrounded process); observed a clean exit and
    # mprime.pid removed on its own afterward.
    os.kill(status["pid"], signal.SIGINT)
    return {"stopping": True, "pid": status["pid"]}


ACTIONS = {
    "start": start,
    "stop": stop,
}
