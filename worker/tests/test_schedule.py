import datetime

from grid_worker import schedule as schedule_mod


def _freeze_hour(monkeypatch, hour: int) -> None:
    class FrozenDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 1, hour, 0)

    monkeypatch.setattr(schedule_mod.datetime, "datetime", FrozenDatetime)


def test_schedule_policy_from_dict_defaults():
    policy = schedule_mod.SchedulePolicy.from_dict({})
    assert policy.enabled is False
    assert policy.active_start_hour == 22
    assert policy.active_end_hour == 6
    assert policy.idle_threshold_minutes == 3


def test_schedule_policy_from_dict_overrides():
    policy = schedule_mod.SchedulePolicy.from_dict(
        {
            "enabled": True,
            "restrict_hours": True,
            "active_start_hour": 9,
            "active_end_hour": 17,
            "only_when_idle": True,
            "idle_threshold_minutes": 10,
        }
    )
    assert policy.enabled is True
    assert policy.active_start_hour == 9
    assert policy.idle_threshold_minutes == 10


def test_within_active_hours_equal_bounds_means_unrestricted():
    # start == end is BOINC's own convention for "no restriction" -- see
    # boinc-backend's apply_schedule(), which relies on the same rule.
    assert schedule_mod._within_active_hours(5, 5) is True


def test_within_active_hours_normal_range(monkeypatch):
    _freeze_hour(monkeypatch, 10)
    assert schedule_mod._within_active_hours(9, 17) is True
    assert schedule_mod._within_active_hours(18, 22) is False


def test_within_active_hours_wraps_past_midnight(monkeypatch):
    _freeze_hour(monkeypatch, 23)
    assert schedule_mod._within_active_hours(22, 6) is True

    _freeze_hour(monkeypatch, 2)
    assert schedule_mod._within_active_hours(22, 6) is True

    _freeze_hour(monkeypatch, 14)
    assert schedule_mod._within_active_hours(22, 6) is False

    _freeze_hour(monkeypatch, 6)
    # end_hour itself is exclusive (0 <= now < end), matching the
    # non-wrapping branch's convention.
    assert schedule_mod._within_active_hours(22, 6) is False


def test_should_run_disabled_ignores_everything():
    policy = schedule_mod.SchedulePolicy(enabled=False, restrict_hours=True, active_start_hour=0, active_end_hour=0)
    assert schedule_mod.should_run(policy) is True


def test_should_run_respects_hour_restriction(monkeypatch):
    _freeze_hour(monkeypatch, 14)
    policy = schedule_mod.SchedulePolicy(enabled=True, restrict_hours=True, active_start_hour=22, active_end_hour=6)
    assert schedule_mod.should_run(policy) is False

    _freeze_hour(monkeypatch, 23)
    assert schedule_mod.should_run(policy) is True


def test_should_run_respects_idle_check(monkeypatch):
    policy = schedule_mod.SchedulePolicy(enabled=True, only_when_idle=True)

    monkeypatch.setattr(schedule_mod, "_is_idle", lambda: False)
    assert schedule_mod.should_run(policy) is False

    monkeypatch.setattr(schedule_mod, "_is_idle", lambda: True)
    assert schedule_mod.should_run(policy) is True


def test_should_run_fails_open_when_idle_unknown(monkeypatch):
    """If idle detection can't determine an answer (no logind, no
    session), we must not block a worker from ever running."""
    policy = schedule_mod.SchedulePolicy(enabled=True, only_when_idle=True)
    monkeypatch.setattr(schedule_mod, "_is_idle", lambda: None)
    assert schedule_mod.should_run(policy) is True


def test_policy_holder_get_set():
    holder = schedule_mod.PolicyHolder()
    assert holder.get().enabled is False

    holder.set(schedule_mod.SchedulePolicy(enabled=True))
    assert holder.get().enabled is True
