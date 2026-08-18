import os

from grid_worker.backends import boinc

SAMPLE_GUI_INFO = """
======== Projects ========
1) -----------
   name: World Community Grid
   master URL: https://www.worldcommunitygrid.org/
   suspended via GUI: no
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

SAMPLE_CC_STATUS = """
======== Client status ========
task mode: auto
task mode perm: auto
network mode: auto
"""


def test_parse_blocks_projects():
    blocks = boinc._parse_blocks(SAMPLE_GUI_INFO)
    assert len(blocks["Projects"]) == 2
    assert blocks["Projects"][0]["name"] == "World Community Grid"
    assert blocks["Projects"][0]["suspended via GUI"] == "no"
    assert blocks["Projects"][1]["suspended via GUI"] == "yes"


def test_parse_blocks_tasks():
    blocks = boinc._parse_blocks(SAMPLE_GUI_INFO)
    assert len(blocks["Tasks"]) == 2
    assert blocks["Tasks"][0]["name"] == "wu_12345_0"
    assert blocks["Tasks"][0]["active_task_state"] == "EXECUTING"
    assert blocks["Tasks"][0]["fraction done"] == "0.482913"


def test_find_field():
    assert boinc._find_field(SAMPLE_CC_STATUS, "task mode") == "auto"
    assert boinc._find_field(SAMPLE_CC_STATUS, "nonexistent field") is None


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

    assert status["run_mode"] == "auto"
    assert len(status["projects"]) == 2
    assert status["projects"][0]["suspended"] is False
    assert status["projects"][1]["suspended"] is True
    assert len(status["tasks"]) == 2
    assert status["tasks"][0]["fraction_done"] == 0.482913
    assert status["tasks"][1]["state"] == "SUSPENDED"


def test_suspend_project_calls_boinccmd_correctly(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    boinc.suspend_project("https://example.org/project/")
    assert calls == [("--project", "https://example.org/project/", "suspend")]


def test_attach_project_calls_boinccmd_correctly(monkeypatch):
    calls = []
    monkeypatch.setattr(boinc, "_run", lambda *args: calls.append(args))
    result = boinc.attach_project("https://example.org/project/", "abc123authenticator")
    assert calls == [("--project_attach", "https://example.org/project/", "abc123authenticator")]
    assert result == {"project_url": "https://example.org/project/", "attached": True}


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
