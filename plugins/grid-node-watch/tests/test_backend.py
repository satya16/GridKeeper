import json
import os
import signal
import stat
import subprocess
import time

import pytest

from grid_node_watch import backend

# Deliberately not "watch-only" in the mprime sense -- the whole point of
# this fixture is to be a stand-in for "some arbitrary long-running
# program", identifiable in the process list by a name unlikely to
# collide with anything actually running on the test machine.
FAKE_TARGET = """#!/bin/bash
trap 'exit 0' TERM
while true; do sleep 0.05; done
"""


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture()
def watch_env(tmp_path, monkeypatch):
    fake_bin = tmp_path / "fake-watch-target.sh"
    fake_bin.write_text(FAKE_TARGET)
    fake_bin.chmod(fake_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    config_path = tmp_path / "targets.json"
    monkeypatch.setenv("GRIDKEEPER_WATCH_CONFIG", str(config_path))
    monkeypatch.setenv("GRIDKEEPER_WATCH_DIR", str(tmp_path))

    def write_config(targets):
        config_path.write_text(json.dumps({"targets": targets}))

    return {"dir": tmp_path, "bin": fake_bin, "write_config": write_config}


def test_is_available_false_with_no_config(watch_env):
    assert backend.is_available() is False


def test_is_available_true_once_a_target_is_configured(watch_env):
    watch_env["write_config"]([{"name": "demo", "match": "fake-watch-target"}])
    assert backend.is_available() is True


def test_is_available_false_on_malformed_config(watch_env):
    watch_env["dir"].joinpath("targets.json").write_text("not json")
    assert backend.is_available() is False


def test_get_status_not_running_when_no_matching_process(watch_env):
    watch_env["write_config"]([{"name": "demo", "match": "fake-watch-target"}])
    status = backend.get_status()
    assert status == {"demo": {"running": False, "pid": None, "has_start_cmd": False}}


def test_get_status_finds_a_process_it_did_not_start(watch_env):
    # Proves the core "watch any program" claim: a process launched
    # completely outside grid-node-watch (here, directly by the test) is
    # still discovered and reported on, the same way it would be for a
    # program a human started by hand on a real machine.
    watch_env["write_config"]([{"name": "demo", "match": "fake-watch-target"}])
    proc = subprocess.Popen([str(watch_env["bin"])])
    try:
        assert _wait_until(lambda: backend.get_status()["demo"]["running"] is True)
        status = backend.get_status()["demo"]
        assert status["pid"] == proc.pid
        assert status["cpu_percent"] is not None
        assert status["uptime_seconds"] >= 0
        assert status["has_start_cmd"] is False
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_get_status_does_not_match_target_name_buried_in_an_unrelated_argument(watch_env):
    # Regression test for a real false positive found live 2026-08-24:
    # matching used to scan the *entire* command line, so a target name
    # that merely appeared as data inside some other process's argument
    # (here, a shell command whose argument text happens to contain
    # "demo-app") was wrongly reported as the target running.
    watch_env["write_config"]([{"name": "demo", "match": "demo-app"}])
    unrelated = subprocess.Popen(
        ["bash", "-c", "echo 'this line mentions demo-app as plain text' >/dev/null; sleep 2"]
    )
    try:
        assert _wait_until(lambda: unrelated.poll() is None, timeout=1.0)
        status = backend.get_status()["demo"]
        assert status["running"] is False
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=2)


def test_start_refuses_without_start_cmd(watch_env):
    watch_env["write_config"]([{"name": "demo", "match": "fake-watch-target"}])
    with pytest.raises(backend.WatchError, match="watch-only"):
        backend.start({"target": "demo"})


def test_start_requires_target_in_payload(watch_env):
    watch_env["write_config"]([{"name": "demo", "match": "fake-watch-target"}])
    with pytest.raises(backend.WatchError, match="target"):
        backend.start({})


def test_start_unknown_target_raises(watch_env):
    watch_env["write_config"]([{"name": "demo", "match": "fake-watch-target"}])
    with pytest.raises(backend.WatchError, match="no watch target"):
        backend.start({"target": "nope"})


def test_start_stop_round_trip(watch_env):
    watch_env["write_config"](
        [{"name": "demo", "match": "fake-watch-target", "start_cmd": [str(watch_env["bin"])]}]
    )

    result = backend.start({"target": "demo"})
    assert result["started"] is True
    assert _wait_until(lambda: backend.get_status()["demo"]["running"] is True)

    again = backend.start({"target": "demo"})
    assert again["already_running"] is True

    stop_result = backend.stop({"target": "demo"})
    assert stop_result["stopping"] is True
    assert _wait_until(lambda: backend.get_status()["demo"]["running"] is False)

    assert backend.stop({"target": "demo"}) == {"already_stopped": True}


def test_stop_uses_configured_signal(watch_env, monkeypatch):
    watch_env["write_config"](
        [{"name": "demo", "match": "fake-watch-target", "start_cmd": [str(watch_env["bin"])], "stop_signal": "SIGKILL"}]
    )
    calls = []
    real_kill = os.kill

    def spy_kill(pid, sig):
        calls.append(sig)
        real_kill(pid, sig)

    monkeypatch.setattr(backend.os, "kill", spy_kill)

    backend.start({"target": "demo"})
    assert _wait_until(lambda: backend.get_status()["demo"]["running"] is True)
    backend.stop({"target": "demo"})
    assert calls == [signal.SIGKILL]


def test_actions_dict_matches_grid_node_backend_interface():
    assert backend.NAME == "watch"
    assert isinstance(backend.LABEL, str)
    assert callable(backend.is_available)
    assert callable(backend.get_status)
    assert set(backend.ACTIONS) == {"start", "stop"}
    assert all(callable(fn) for fn in backend.ACTIONS.values())
    assert not hasattr(backend, "CREDENTIAL_ACTION") or backend.CREDENTIAL_ACTION is None
