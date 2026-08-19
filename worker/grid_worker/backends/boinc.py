"""Controls a locally-installed BOINC client via the `boinccmd` CLI tool.

Shelling out to boinccmd (rather than speaking BOINC's GUI RPC protocol
directly over port 31416) trades a bit of parsing fragility for a lot of
simplicity -- no RPC auth handshake to implement, and boinccmd is installed
alongside boinc-client on every distro. If boinccmd's text output format
turns out to vary across versions in practice, swap this for the RPC
protocol (see docs/REQUIREMENTS.md section 4) without touching callers --
they only see the dict shapes returned below.
"""

import os
import re
import shutil
import subprocess
import tempfile

BOINCCMD = "boinccmd"


class BoincError(RuntimeError):
    pass


def is_available() -> bool:
    return shutil.which(BOINCCMD) is not None


def _run(*args: str) -> str:
    try:
        proc = subprocess.run(
            [BOINCCMD, *args],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError as e:
        raise BoincError(f"{BOINCCMD} not found on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise BoincError(f"{BOINCCMD} {' '.join(args)} timed out") from e
    if proc.returncode != 0:
        raise BoincError(f"{BOINCCMD} {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


_SECTION_RE = re.compile(r"={4,}\s*(.+?)\s*={4,}")
_BLOCK_RE = re.compile(r"^\s*\d+\)\s*-+")


def _parse_blocks(text: str) -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {}
    current_section: str | None = None
    current_block: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        section_match = _SECTION_RE.match(line.strip())
        if section_match:
            current_section = section_match.group(1)
            sections[current_section] = []
            current_block = None
            continue
        if _BLOCK_RE.match(line):
            current_block = {}
            if current_section is not None:
                sections[current_section].append(current_block)
            continue
        if current_block is not None and ":" in line:
            key, _, value = line.strip().partition(":")
            # first-occurrence wins: a project block's top-level fields (name,
            # master URL, ...) come before its nested "GUI URL:" sub-entries,
            # which repeat field names like "name"/"URL" for the link itself --
            # confirmed live 2026-08-18 against Einstein@Home, where the last
            # GUI URL's name ("GEO600 project") was clobbering the real
            # project name before this fix (see knowledge-graph/boinc-backend.md)
            current_block.setdefault(key.strip(), value.strip())
    return sections


def _find_field(text: str, field_name: str) -> str | None:
    match = re.search(rf"{re.escape(field_name)}:\s*(.+)", text)
    return match.group(1).strip() if match else None


def _cpu_suspend_reason(cc_status: str) -> str | None:
    """CPU section only -- e.g. "on batteries", "user request", "always".

    Deliberately scoped to just the CPU section (not a plain _find_field
    search over the whole text): GPU/Network status can also carry their
    own "suspended: <reason>" line, and a naive first-match search would
    misattribute a GPU-only suspension as the reason CPU work isn't
    running. When CPU isn't suspended, its line reads "not suspended"
    (no colon), which this correctly reports as None.
    """
    section = re.search(r"CPU status\s*\n(.*?)(?:\nGPU status|\Z)", cc_status, re.DOTALL)
    if not section:
        return None
    return _find_field(section.group(1), "suspended")


def get_status() -> dict:
    """Returns {"run_mode": str, "cpu_suspend_reason": str | None, "projects": [...], "tasks": [...]}."""
    gui_info = _run("--get_simple_gui_info")
    blocks = _parse_blocks(gui_info)

    projects = []
    for p in blocks.get("Projects", []):
        projects.append(
            {
                "url": p.get("master URL", ""),
                "name": p.get("name", p.get("master URL", "unknown")),
                "suspended": p.get("suspended via GUI", "no").lower() == "yes",
            }
        )

    tasks = []
    for t in blocks.get("Tasks", []):
        try:
            fraction_done = float(t.get("fraction done", "0"))
        except ValueError:
            fraction_done = 0.0
        tasks.append(
            {
                "name": t.get("name", "unknown"),
                "project_url": t.get("project URL", ""),
                "state": t.get("active_task_state", t.get("state", "unknown")),
                "fraction_done": fraction_done,
            }
        )

    cc_status = _run("--get_cc_status")
    # Confirmed live 2026-08-18 against a real daemon (BOINC 8.2.15,
    # official release build -- see knowledge-graph/boinc-backend.md):
    # --get_cc_status has no "task mode:" line at all in this version.
    # Run mode lives under the "CPU status" section as "current mode:"
    # (that section comes first, before "GPU status"/"Network status",
    # each of which also has their own "current mode:" line -- this
    # regex matches the first occurrence, i.e. CPU's).
    run_mode = _find_field(cc_status, "current mode") or "unknown"
    cpu_suspend_reason = _cpu_suspend_reason(cc_status)

    return {
        "run_mode": run_mode,
        "cpu_suspend_reason": cpu_suspend_reason,
        "projects": projects,
        "tasks": tasks,
    }


def suspend_project(project_url: str) -> dict:
    _run("--project", project_url, "suspend")
    return {"project_url": project_url, "suspended": True}


def resume_project(project_url: str) -> dict:
    _run("--project", project_url, "resume")
    return {"project_url": project_url, "suspended": False}


def attach_project(project_url: str, account_key: str) -> dict:
    """account_key is the project account's authenticator (from that
    project's "your account" web page, or via --lookup_account) -- a
    long-lived credential, not a one-time thing like a pairing token.
    Callers (manager/app/api/workers.py) must not persist it in plaintext
    -- see that module's payload redaction."""
    _run("--project_attach", project_url, account_key)
    return {"project_url": project_url, "attached": True}


def detach_project(project_url: str) -> dict:
    _run("--project", project_url, "detach")
    return {"project_url": project_url, "detached": True}


def suspend_all() -> dict:
    _run("--set_run_mode", "never")
    return {"run_mode": "never"}


def resume_all() -> dict:
    _run("--set_run_mode", "auto")
    return {"run_mode": "auto"}


_GLOBAL_PREFS_OVERRIDE_TEMPLATE = """<global_preferences>
   <run_if_user_active>{run_if_user_active}</run_if_user_active>
   <run_gpu_if_user_active>{run_if_user_active}</run_gpu_if_user_active>
   <idle_time_to_run>{idle_time_to_run}</idle_time_to_run>
   <start_hour>{start_hour}</start_hour>
   <end_hour>{end_hour}</end_hour>
</global_preferences>
"""


def apply_schedule(policy: dict) -> dict:
    """Pushes hour/idle restrictions into BOINC's own preferences engine
    (global_prefs_override.xml) rather than polling and suspending
    ourselves -- BOINC already does idle detection and hour-of-day
    scheduling natively and does it better than we could from outside.

    `--set_global_prefs_override <file>` and `--read_global_prefs_override`
    are documented boinccmd options, but this hasn't been run against a
    live boinccmd in the environment this was written in -- verify the
    prefs actually took with `boinccmd --get_global_prefs_override` (or
    watch BOINC Manager's Activity behavior) the first time you use this.
    """
    enabled = bool(policy.get("enabled", False))
    restrict_hours = enabled and bool(policy.get("restrict_hours", False))
    only_when_idle = enabled and bool(policy.get("only_when_idle", False))

    xml = _GLOBAL_PREFS_OVERRIDE_TEMPLATE.format(
        run_if_user_active=0 if only_when_idle else 1,
        idle_time_to_run=int(policy.get("idle_threshold_minutes", 3)) if only_when_idle else 0,
        start_hour=int(policy.get("active_start_hour", 0)) if restrict_hours else 0,
        end_hour=int(policy.get("active_end_hour", 0)) if restrict_hours else 0,
    )

    fd, path = tempfile.mkstemp(suffix=".xml", prefix="grid-worker-boinc-prefs-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(xml)
        _run("--set_global_prefs_override", path)
        _run("--read_global_prefs_override")
    finally:
        os.unlink(path)

    return {"applied": True, "enabled": enabled}


ACTIONS = {
    "suspend_project": lambda payload: suspend_project(payload["project_url"]),
    "resume_project": lambda payload: resume_project(payload["project_url"]),
    "attach_project": lambda payload: attach_project(payload["project_url"], payload["account_key"]),
    "detach_project": lambda payload: detach_project(payload["project_url"]),
    "suspend_all": lambda payload: suspend_all(),
    "resume_all": lambda payload: resume_all(),
}
