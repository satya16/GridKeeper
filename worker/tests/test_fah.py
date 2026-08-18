from grid_worker.backends import fah


def test_get_status_maps_units_dict_to_slots(monkeypatch):
    """Field shape confirmed 2026-08-18 against a real assigned work unit
    (project 18292) -- the project number lives under "assignment", not
    "wu" (that dict actually holds run/clone/gen/collection-server info,
    no project field at all)."""
    state = {
        "units": {
            "0": {
                "group": "",
                "state": "RUN",
                "progress": 0.425,
                "assignment": {"project": 17106},
                "wu": {"run": 1368, "clone": 2, "gen": 12},
            }
        }
    }
    monkeypatch.setattr(fah, "_get_state", lambda: state)
    status = fah.get_status()

    assert len(status["slots"]) == 1
    assert status["slots"][0]["id"] == ""
    assert status["slots"][0]["status"] == "RUN"
    assert status["slots"][0]["progress"] == 0.425
    assert status["slots"][0]["project"] == "17106"


def test_get_status_units_as_list(monkeypatch):
    """units can also arrive as a JSON list depending on client version --
    handle both shapes rather than assuming a dict."""
    state = {"units": [{"group": "gpu", "state": "RUN", "progress": 0.1}]}
    monkeypatch.setattr(fah, "_get_state", lambda: state)
    status = fah.get_status()

    assert status["slots"][0]["id"] == "gpu"
    assert status["slots"][0]["project"] is None


def test_get_status_no_units_returns_empty_slots(monkeypatch):
    monkeypatch.setattr(fah, "_get_state", lambda: {})
    status = fah.get_status()
    assert status["slots"] == []


def test_get_status_includes_account_info_without_passkey(monkeypatch):
    state = {
        "units": [],
        "config": {"user": "TestUser", "team": 12345, "passkey": "secretpasskey123", "fold_anon": True, "cause": "cancer"},
    }
    monkeypatch.setattr(fah, "_get_state", lambda: state)
    status = fah.get_status()

    assert status["account"] == {"user": "TestUser", "team": 12345, "cause": "cancer", "fold_anon": True}
    assert "secretpasskey123" not in str(status)


def test_get_status_account_defaults_when_no_config(monkeypatch):
    monkeypatch.setattr(fah, "_get_state", lambda: {})
    status = fah.get_status()
    assert status["account"] == {"user": "Anonymous", "team": 0, "cause": "any", "fold_anon": False}


def test_set_config_sends_correct_payload(monkeypatch):
    sent = []
    monkeypatch.setattr(fah, "_send_command", lambda payload, **kwargs: sent.append(payload))
    result = fah.set_config({"cause": "cancer", "fold_anon": True})
    assert sent == [{"cmd": "config", "config": {"cause": "cancer", "fold_anon": True}}]
    assert result == {"updated": ["cause", "fold_anon"]}


def test_set_config_rejects_unknown_fields(monkeypatch):
    monkeypatch.setattr(fah, "_send_command", lambda payload, **kwargs: None)
    try:
        fah.set_config({"cpus": 4})
        raise AssertionError("expected FahError")
    except fah.FahError as e:
        assert "cpus" in str(e)


def test_set_config_action_dispatches_full_payload(monkeypatch):
    calls = []
    monkeypatch.setattr(fah, "set_config", lambda fields: calls.append(fields))
    fah.ACTIONS["set_config"]({"user": "TestUser", "passkey": "abc"})
    assert calls == [{"user": "TestUser", "passkey": "abc"}]


def test_pause_all_sends_correct_payload(monkeypatch):
    sent = []
    monkeypatch.setattr(fah, "_send_command", lambda payload, **kwargs: sent.append(payload))
    fah.pause_all()
    assert sent == [{"cmd": "pause"}]


def test_unpause_all_sends_correct_payload(monkeypatch):
    sent = []
    monkeypatch.setattr(fah, "_send_command", lambda payload, **kwargs: sent.append(payload))
    fah.unpause_all()
    assert sent == [{"cmd": "unpause"}]


def test_pause_slot_acts_globally(monkeypatch):
    """FAHClient 8.1.18 has no per-group/per-slot control (verified live --
    see module docstring), so pause_slot degrades to a global pause."""
    sent = []
    monkeypatch.setattr(fah, "_send_command", lambda payload, **kwargs: sent.append(payload))
    result = fah.pause_slot("gpu")
    assert sent == [{"cmd": "pause"}]
    assert result == {"slot_id": "gpu", "paused": True}


def test_unpause_slot_acts_globally(monkeypatch):
    sent = []
    monkeypatch.setattr(fah, "_send_command", lambda payload, **kwargs: sent.append(payload))
    result = fah.unpause_slot("gpu")
    assert sent == [{"cmd": "unpause"}]
    assert result == {"slot_id": "gpu", "paused": False}
