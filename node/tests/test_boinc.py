import os

from grid_node.backends import boinc

SAMPLE_GUI_INFO = """
======== Projects ========
1) -----------
   name: World Community Grid
   master URL: https://www.worldcommunitygrid.org/
   suspended via GUI: no
GUI URL:
   name: Your account
   description: View and modify your account profile
   URL: https://www.worldcommunitygrid.org/account
GUI URL:
   name: GEO600 project
   description: The home page of the GEO600 project
   URL: http://www.geo600.org
2) -----------
   name: Rosetta@home
   master URL: https://boinc.bakerlab.org/rosetta/
   suspended via GUI: yes
======== Tasks ========
1) -----------
   name: wu_12345_0
   project URL: https://www.worldcommunitygrid.org/
   active_task_state: EXECUTING
   fraction done: 0.482913
2) -----------
   name: wu_67890_1
   project URL: https://boinc.bakerlab.org/rosetta/
   state: SUSPENDED
   fraction done: 0.100000
"""

# Real output, confirmed live 2026-08-18 against BOINC 8.2.15 (official
# release build) -- boinccmd --get_cc_status has no "task mode:" line at
# all; run mode lives under "CPU status" as "current mode:". Originally
# written from documentation/memory as "task mode: auto" under a
# "======== Client status ========" header, which never matched any real
# output -- see knowledge-graph/boinc-backend.md.
SAMPLE_CC_STATUS = """
network connection status: don't need connection
CPU status
    not suspended
    current mode: according to prefs
    perm mode: according to prefs
    perm becomes current in 0 sec
GPU status
    not suspended
    current mode: according to prefs
    perm mode: according to prefs
    perm becomes current in 0 sec
Network status
    not suspended
    current mode: according to prefs
    perm mode: according to prefs
    perm becomes current in 0 sec
"""

# Real output, confirmed live 2026-08-19 on a laptop running on battery --
# BOINC's own preference is to not crunch on battery power by default, and
# reports it via this CPU-section-only "suspended: on batteries" line.
SAMPLE_CC_STATUS_ON_BATTERY = """
network connection status: don't need connection
CPU status
    suspended: on batteries
    current mode: according to prefs
    perm mode: according to prefs
    perm becomes current in 0 sec
GPU status
    not suspended
    current mode: according to prefs
    perm mode: according to prefs
    perm becomes current in 0 sec
Network status
    not suspended
    current mode: according to prefs
    perm mode: according to prefs
    perm becomes current in 0 sec
"""


def test_parse_blocks_projects():
    blocks = boinc._parse_blocks(SAMPLE_GUI_INFO)
    assert len(blocks["Projects"]) == 2
    # project 1's nested "GUI URL:" sub-entries repeat the "name" key for the
    # link itself (e.g. "GEO600 project") -- must not clobber the real
    # project-level name, confirmed live 2026-08-18 against Einstein@Home
    assert blocks["Projects"][0]["name"] == "World Community Grid"
    assert blocks["Projects"][0]["master URL"] == "https://www.worldcommunitygrid.org/"
    assert blocks["Projects"][0]["suspended via GUI"] == "no"
    assert blocks["Projects"][1]["suspended via GUI"] == "yes"


def test_parse_blocks_tasks():
    blocks = boinc._parse_blocks(SAMPLE_GUI_INFO)
    assert len(blocks["Tasks"]) == 2
    assert blocks["Tasks"][0]["name"] == "wu_12345_0"
    assert blocks["Tasks"][0]["active_task_state"] == "EXECUTING"
    assert blocks["Tasks"][0]["fraction done"] == "0.482913"


def test_find_field():
    # Matches the CPU section's "current mode" -- the first occurrence in
    # the text, since CPU status comes before GPU/Network status and all
    # three sections share the same field name.
    assert boinc._find_field(SAMPLE_CC_STATUS, "current mode") == "according to prefs"
    assert boinc._find_field(SAMPLE_CC_STATUS, "nonexistent field") is None


def test_cpu_suspend_reason_none_when_not_suspended():
    assert boinc._cpu_suspend_reason(SAMPLE_CC_STATUS) is None


def test_cpu_suspend_reason_on_battery():
    assert boinc._cpu_suspend_reason(SAMPLE_CC_STATUS_ON_BATTERY) == "on batteries"


def test_cpu_suspend_reason_ignores_gpu_only_suspension():
    # GPU can carry its own "suspended: <reason>" line -- must not be
    # misattributed to the CPU as the reason work isn't running.
    text = SAMPLE_CC_STATUS.replace(
        "GPU status\n    not suspended", "GPU status\n    suspended: user request"
    )
    assert boinc._cpu_suspend_reason(text) is None


def test_is_available_false_when_missing(monkeypatch):
    monkeypatch.setattr(boinc.shutil, "which", lambda name: None)
    assert boinc.is_available() is False


def test_is_available_true_when_present(monkeypatch):
    monkeypatch.setattr(boinc.shutil, "which", lambda name: "/usr/bin/boinccmd")
    assert boinc.is_available() is True


def test_get_status_end_to_end(monkeypatch):
    def fake_run(*args):
        if args[0] == "--get_simple_gui_info":
            return SAMPLE_GUI_INFO
        if args[0] == "--get_cc_status":
            return SAMPLE_CC_STATUS
        raise AssertionError(f"unexpected boinccmd args: {args}")

    monkeypatch.setattr(boinc, "_run", fake_run)
    status = boinc.get_status()

    assert status["run_mode"] == "according to prefs"
    assert status["cpu_suspend_reason"] is None
    assert len(status["projects"]) == 2
    assert status["projects"][0]["name"] == "World Community Grid"
    assert status["projects"][0]["url"] == "https://www.worldcommunitygrid.org/"
    assert status["projects"][0]["suspended"] is False
    assert status["projects"][1]["url"] == "https://boinc.bakerlab.org/rosetta/"
    assert status["projects"][1]["suspended"] is True
    assert len(status["tasks"]) == 2
    assert status["tasks"][0]["fraction_done"] == 0.482913
    assert status["tasks"][1]["state"] == "SUSPENDED"


def test_get_status_reports_cpu_suspend_reason_on_battery(monkeypatch):
    def fake_run(*args):
        if args[0] == "--get_simple_gui_info":
            return SAMPLE_GUI_INFO
        if args[0] == "--get_cc_status":
            return SAMPLE_CC_STATUS_ON_BATTERY
        raise AssertionError(f"unexpected boinccmd args: {args}")

    monkeypatch.setattr(boinc, "_run", fake_run)
    status = boinc.get_status()

    assert status["cpu_suspend_reason"] == "on batteries"


def test_suspend_project_calls_boinccmd_correctly(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    boinc.suspend_project("https://example.org/project/")
    assert calls == [("--project", "https://example.org/project/", "suspend")]


def test_attach_project_calls_boinccmd_correctly(monkeypatch):
    monkeypatch.setattr(boinc, "get_status", lambda: {"projects": [], "tasks": []})
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    result = boinc.attach_project("https://example.org/project/", "abc123authenticator")
    assert calls == [("--project_attach", "https://example.org/project/", "abc123authenticator")]
    assert result == {"project_url": "https://example.org/project/", "attached": True}


def test_attach_project_skips_call_when_already_attached(monkeypatch):
    """Guards against a real BOINC quirk confirmed live 2026-08-19: a
    repeat --project_attach call for an already-attached project isn't
    reliably rejected by BOINC itself, and can silently create a
    duplicate project entry instead."""
    monkeypatch.setattr(
        boinc,
        "get_status",
        lambda: {"projects": [{"url": "https://example.org/project/", "name": "Example", "suspended": False}], "tasks": []},
    )
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    result = boinc.attach_project("https://example.org/project/", "abc123authenticator")
    assert calls == []
    assert result == {"project_url": "https://example.org/project/", "attached": True, "already_attached": True}


def test_detach_project_calls_boinccmd_correctly(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    result = boinc.detach_project("https://example.org/project/")
    assert calls == [("--project", "https://example.org/project/", "detach")]
    assert result == {"project_url": "https://example.org/project/", "detached": True}


def test_attach_project_action_reads_payload_fields(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "attach_project", lambda url, key: calls.append((url, key)))
    boinc.ACTIONS["attach_project"]({"project_url": "https://example.org/", "account_key": "secret"})
    assert calls == [("https://example.org/", "secret")]


def test_suspend_all_sets_never_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    result = boinc.suspend_all()
    assert calls == [("--set_run_mode", "never")]
    assert result == {"run_mode": "never"}


def test_resume_all_sets_auto_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    result = boinc.resume_all()
    assert calls == [("--set_run_mode", "auto")]
    assert result == {"run_mode": "auto"}


def test_apply_schedule_enabled_writes_restrictions(monkeypatch):
    written = {}

    def fake_run(*args):
        if args[0] == "--set_global_prefs_override":
            written["content"] = open(args[1]).read()
        return ""

    monkeypatch.setattr(boinc, "_run", fake_run)
    result = boinc.apply_schedule(
        {
            "enabled": True,
            "restrict_hours": True,
            "active_start_hour": 22,
            "active_end_hour": 6,
            "only_when_idle": True,
            "idle_threshold_minutes": 5,
        }
    )

    assert result == {"applied": True, "enabled": True}
    assert "<start_hour>22</start_hour>" in written["content"]
    assert "<end_hour>6</end_hour>" in written["content"]
    assert "<idle_time_to_run>5</idle_time_to_run>" in written["content"]
    assert "<run_if_user_active>0</run_if_user_active>" in written["content"]


def test_apply_schedule_disabled_writes_no_restriction(monkeypatch):
    written = {}

    def fake_run(*args):
        if args[0] == "--set_global_prefs_override":
            written["content"] = open(args[1]).read()
        return ""

    monkeypatch.setattr(boinc, "_run", fake_run)
    boinc.apply_schedule({"enabled": False})

    assert "<start_hour>0</start_hour>" in written["content"]
    assert "<end_hour>0</end_hour>" in written["content"]
    assert "<run_if_user_active>1</run_if_user_active>" in written["content"]


def test_apply_schedule_cleans_up_temp_file(monkeypatch):
    captured_path = {}

    def fake_run(*args):
        if args[0] == "--set_global_prefs_override":
            captured_path["path"] = args[1]
            assert os.path.exists(args[1])
        return ""

    monkeypatch.setattr(boinc, "_run", fake_run)
    boinc.apply_schedule({"enabled": False})
    assert not os.path.exists(captured_path["path"])
