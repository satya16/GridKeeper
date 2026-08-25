from app.connections import connections
from .conftest import seed_capabilities


def test_list_backends_returns_seeded_boinc_and_fah(auth_client):
    resp = auth_client.get("/api/backends")
    assert resp.status_code == 200
    names = {b["name"] for b in resp.json()}
    assert names == {"boinc", "fah"}
    boinc = next(b for b in resp.json() if b["name"] == "boinc")
    assert boinc["label"] == "BOINC"
    assert boinc["credential_action"]["action"] == "attach_project"
    assert boinc["sensitive_fields"] == {"attach_project": ["account_key"]}


def test_list_backends_requires_auth(client):
    resp = client.get("/api/backends")
    assert resp.status_code == 401


def test_status_frame_capabilities_upsert_new_backend(auth_client):
    """Simulates a third-party plugin's node reporting a backend the hub
    has never seen -- see node/grid_node/daemon.py's status frame and
    main.py's node_ws capabilities upsert."""
    seed_capabilities(
        {
            "gimps": {
                "label": "GIMPS (mprime)",
                "sensitive_fields": {},
                "credential_action": None,
                "actions": ["start", "stop"],
            }
        }
    )
    resp = auth_client.get("/api/backends")
    names = {b["name"] for b in resp.json()}
    assert "gimps" in names
    gimps = next(b for b in resp.json() if b["name"] == "gimps")
    assert gimps["credential_action"] is None
    assert gimps["actions"] == ["start", "stop"]


def test_status_frame_capabilities_upsert_overwrites_existing(auth_client):
    seed_capabilities(
        {"boinc": {"label": "BOINC (newer plugin build)", "sensitive_fields": {}, "credential_action": None, "actions": ["ping"]}}
    )
    boinc = next(b for b in auth_client.get("/api/backends").json() if b["name"] == "boinc")
    assert boinc["label"] == "BOINC (newer plugin build)"
    assert boinc["actions"] == ["ping"]


def _enroll(auth_client, name: str = "node-1") -> dict:
    token = auth_client.post("/api/pairing-tokens", json={"label": ""}).json()["token"]
    resp = auth_client.post(
        "/api/enroll", json={"pairing_token": token, "name": name, "os_name": "linux", "backends": ["boinc"]}
    )
    assert resp.status_code == 200
    return resp.json()


def test_command_for_backend_hub_has_never_heard_of_is_not_redacted(auth_client, monkeypatch):
    """Documented, expected edge case: redaction is sourced from the
    BackendCapability registry (see nodes.py::_redact_payload), which is
    only populated once some node has reported that backend's status
    frame. In practice a node reports capabilities on its very first
    status frame, before an admin could plausibly issue it a command --
    this test exists to make the boundary explicit, not to claim it's a
    gap that needs fixing."""
    enrolled = _enroll(auth_client)
    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = auth_client.post(
        f"/api/nodes/{enrolled['node_id']}/commands",
        json={"backend": "mystery-backend", "action": "do-a-secret-thing", "payload": {"api_key": "not-yet-known-as-sensitive"}},
    )
    assert resp.status_code == 200
    assert resp.json()["payload"]["api_key"] == "not-yet-known-as-sensitive"
