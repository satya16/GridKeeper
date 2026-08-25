import types

import pytest

from grid_node.backends import base, discover_backends


def _fake_entry_point(name, module):
    ep = types.SimpleNamespace(name=name, value=f"fake.{name}", load=lambda: module)
    return ep


def test_discover_backends_finds_boinc_and_fah():
    # Subset, not exact-equality: this venv may also have a real
    # third-party plugin installed (e.g. grid-node-gimps, see
    # plugins/grid-node-gimps/) -- discover_backends() finding *more* than
    # the two built-ins is the plugin mechanism working as intended, not a
    # test failure. boinc/fah must always be present regardless.
    backends = discover_backends()
    assert {"boinc", "fah"} <= set(backends)
    assert backends["boinc"].LABEL == "BOINC"
    assert backends["fah"].LABEL == "Folding@home"


def test_validate_backend_rejects_missing_attrs():
    incomplete = types.SimpleNamespace(NAME="broken", LABEL="Broken")
    with pytest.raises(base.InvalidBackend, match="missing required attribute"):
        base.validate_backend(incomplete)


def test_validate_backend_rejects_non_dict_actions():
    bad = types.SimpleNamespace(
        NAME="broken",
        LABEL="Broken",
        is_available=lambda: True,
        get_status=lambda: {},
        ACTIONS=["not", "a", "dict"],
    )
    with pytest.raises(base.InvalidBackend, match="ACTIONS must be a dict"):
        base.validate_backend(bad)


def test_validate_backend_accepts_well_formed_module():
    good = types.SimpleNamespace(
        NAME="ok",
        LABEL="OK",
        is_available=lambda: True,
        get_status=lambda: {},
        ACTIONS={"noop": lambda payload: {}},
    )
    base.validate_backend(good)  # does not raise


def test_discover_backends_skips_invalid_plugin(monkeypatch):
    broken = types.SimpleNamespace(NAME="broken", LABEL="Broken")
    good = types.SimpleNamespace(
        NAME="ok",
        LABEL="OK",
        is_available=lambda: True,
        get_status=lambda: {},
        ACTIONS={"noop": lambda payload: {}},
    )
    monkeypatch.setattr(
        "grid_node.backends.entry_points",
        lambda group: [_fake_entry_point("broken", broken), _fake_entry_point("ok", good)],
    )
    backends = discover_backends()
    assert backends == {"ok": good}


def test_discover_backends_skips_plugin_that_raises_on_load(monkeypatch):
    def _raise():
        raise ImportError("no such module")

    bad_ep = types.SimpleNamespace(name="explodes", value="fake.explodes", load=_raise)
    monkeypatch.setattr("grid_node.backends.entry_points", lambda group: [bad_ep])
    assert discover_backends() == {}


def test_capabilities_reflects_declared_metadata():
    from grid_node.backends import boinc

    caps = base.capabilities(boinc)
    assert caps["label"] == "BOINC"
    assert caps["sensitive_fields"] == {"attach_project": ["account_key"]}
    assert caps["credential_action"] == {
        "action": "attach_project",
        "key_field": "account_key",
        "static_fields": ["project_url"],
    }
    assert "attach_project" in caps["actions"]


def test_capabilities_defaults_when_optional_attrs_absent():
    minimal = types.SimpleNamespace(
        NAME="minimal",
        LABEL="Minimal",
        is_available=lambda: True,
        get_status=lambda: {},
        ACTIONS={"noop": lambda payload: {}},
    )
    caps = base.capabilities(minimal)
    assert caps == {
        "label": "Minimal",
        "sensitive_fields": {},
        "credential_action": None,
        "actions": ["noop"],
    }
