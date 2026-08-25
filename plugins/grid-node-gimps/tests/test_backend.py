import os
import stat
import time

import pytest

from grid_node_gimps import backend

FAKE_MPRIME = """#!/bin/bash
# Stands in for real mprime for tests: writes its own pid file (same
# filename mprime itself uses -- confirmed live 2026-08-24) and traps
# SIGINT to remove it and exit, mirroring mprime's own confirmed-live
# "clean shutdown, pid file gone" behavior on SIGINT.
echo $$ > mprime.pid
trap 'rm -f mprime.pid; exit 0' INT
while true; do sleep 0.05; done
"""


@pytest.fixture()
def gimps_env(tmp_path, monkeypatch):
    work_dir = tmp_path / "gimps-work"
    work_dir.mkdir()
    fake_bin = tmp_path / "mprime"
    fake_bin.write_text(FAKE_MPRIME)
    fake_bin.chmod(fake_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("GRIDKEEPER_GIMPS_DIR", str(work_dir))
    monkeypatch.setenv("GRIDKEEPER_GIMPS_BIN", str(fake_bin))
    return work_dir


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_is_available_true_when_binary_configured(gimps_env):
    assert backend.is_available() is True


def test_is_available_false_when_binary_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("GRIDKEEPER_GIMPS_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir, nothing found
    assert backend.is_available() is False


def test_get_status_not_configured_without_prime_txt(gimps_env):
    status = backend.get_status()
    assert status["configured"] is False
    assert status["running"] is False
    assert status["pid"] is None


def test_start_refuses_when_not_configured(gimps_env):
    with pytest.raises(backend.GimpsError, match="never been set up"):
        backend.start({})


def test_start_stop_round_trip(gimps_env):
    (gimps_env / "prime.txt").write_text("StressTester=1\nUsePrimenet=0\n")

    result = backend.start({})
    assert result["started"] is True
    assert _wait_until(lambda: backend.get_status()["running"] is True)

    status = backend.get_status()
    assert status["running"] is True
    assert status["pid"] is not None
    assert status["configured"] is True

    again = backend.start({})
    assert again == {"already_running": True, "pid": status["pid"]}

    stop_result = backend.stop({})
    assert stop_result["stopping"] is True
    assert _wait_until(lambda: backend.get_status()["running"] is False)

    assert backend.stop({}) == {"already_stopped": True}


def test_get_status_reports_last_log_line(gimps_env):
    (gimps_env / "prime.log").write_text("line one\nline two\nlast line\n")
    assert backend.get_status()["last_log_line"] == "last line"


def test_get_status_last_log_line_none_when_missing(gimps_env):
    assert backend.get_status()["last_log_line"] is None


def test_actions_dict_matches_grid_node_backend_interface():
    # Mirrors node/grid_node/backends/base.py's contract without importing
    # grid_node (this plugin has no runtime dependency on it) -- same
    # required shape a fresh discover_backends() validation pass checks.
    assert backend.NAME == "gimps"
    assert isinstance(backend.LABEL, str)
    assert callable(backend.is_available)
    assert callable(backend.get_status)
    assert set(backend.ACTIONS) == {"start", "stop"}
    assert all(callable(fn) for fn in backend.ACTIONS.values())
    assert not hasattr(backend, "CREDENTIAL_ACTION") or backend.CREDENTIAL_ACTION is None


FAKE_MPRIME_QUICK_EXIT = """#!/bin/bash
# Simulates the real behavior found live: a bare relaunch with no stdin
# lands mprime at its interactive Main Menu and exits almost immediately
# rather than resuming any prior work (see backend.py's module docstring,
# "Known gap, found live"). Used to regression-test that start() reaps it
# instead of leaving a zombie under grid-node's pid.
echo $$ > mprime.pid
rm -f mprime.pid
exit 0
"""


def test_start_reaps_a_quickly_exiting_process_no_zombie(tmp_path, monkeypatch):
    work_dir = tmp_path / "gimps-work"
    work_dir.mkdir()
    (work_dir / "prime.txt").write_text("StressTester=1\nUsePrimenet=0\n")
    fake_bin = tmp_path / "mprime"
    fake_bin.write_text(FAKE_MPRIME_QUICK_EXIT)
    fake_bin.chmod(fake_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("GRIDKEEPER_GIMPS_DIR", str(work_dir))
    monkeypatch.setenv("GRIDKEEPER_GIMPS_BIN", str(fake_bin))

    # Capture the real Popen object start() creates, instead of racing the
    # fake script's own (immediately-deleted) pid file -- .returncode only
    # becomes non-None once something has actually wait()ed on it, so this
    # directly exercises the reaper-thread fix rather than inferring it.
    captured = {}
    real_popen = backend.subprocess.Popen

    def spy_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        captured["proc"] = proc
        return proc

    monkeypatch.setattr(backend.subprocess, "Popen", spy_popen)

    backend.start({})

    assert "proc" in captured
    # Regression guard for the zombie bug found live 2026-08-24: without
    # start()'s reaper thread, .returncode stays None forever even after
    # the child has long since exited, since nothing ever calls wait() on
    # it.
    assert _wait_until(lambda: captured["proc"].returncode is not None, timeout=2.0)
