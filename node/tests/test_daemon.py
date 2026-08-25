import types

import pytest

from grid_node import daemon
from grid_node.schedule import SchedulePolicy


def test_collect_capabilities_covers_only_active_backends():
    caps = daemon.collect_capabilities(["boinc"])
    assert set(caps) == {"boinc"}
    assert caps["boinc"]["credential_action"]["action"] == "attach_project"


def test_apply_native_schedules_calls_backends_declaring_apply_schedule(monkeypatch):
    calls = []
    with_native = types.SimpleNamespace(apply_schedule=lambda policy: calls.append(("with_native", policy)))
    without_native = types.SimpleNamespace()  # no apply_schedule attribute at all
    monkeypatch.setattr(daemon, "BACKENDS", {"with_native": with_native, "without_native": without_native})

    policy = SchedulePolicy(enabled=True, restrict_hours=True, active_start_hour=1, active_end_hour=2)
    daemon._apply_native_schedules(["with_native", "without_native"], policy)

    assert len(calls) == 1
    name, applied_policy = calls[0]
    assert name == "with_native"
    assert applied_policy == policy.to_dict()


def test_apply_native_schedules_tolerates_backend_raising(monkeypatch, caplog):
    def _raise(policy):
        raise RuntimeError("boinccmd exploded")

    flaky = types.SimpleNamespace(apply_schedule=_raise)
    monkeypatch.setattr(daemon, "BACKENDS", {"flaky": flaky})

    # Must not raise -- one backend failing to apply a schedule shouldn't
    # break the command loop or any other backend's schedule application.
    daemon._apply_native_schedules(["flaky"], SchedulePolicy())
