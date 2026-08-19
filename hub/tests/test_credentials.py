import os

from app.connections import connections

from .conftest import AUTH


def _enroll(client, name: str = "node-1") -> dict:
    token = client.post("/api/pairing-tokens", json={"label": ""}, auth=AUTH).json()["token"]
    resp = client.post(
        "/api/enroll", json={"pairing_token": token, "name": name, "os_name": "linux", "backends": ["boinc"]}
    )
    assert resp.status_code == 200
    return resp.json()


def _create_credential(client, name: str = "wcg-lab-account", account_key: str = "supersecret123") -> dict:
    resp = client.post(
        "/api/credentials",
        json={"name": name, "project_url": "https://www.worldcommunitygrid.org/", "account_key": account_key},
        auth=AUTH,
    )
    assert resp.status_code == 200
    return resp.json()


def test_create_credential_never_returns_the_key(client):
    body = _create_credential(client)
    assert body["name"] == "wcg-lab-account"
    assert body["project_url"] == "https://www.worldcommunitygrid.org/"
    assert "account_key" not in body
    assert "key" not in body


def test_create_credential_rejects_duplicate_name(client):
    _create_credential(client)
    resp = client.post(
        "/api/credentials",
        json={"name": "wcg-lab-account", "project_url": "https://example.org/", "account_key": "other"},
        auth=AUTH,
    )
    assert resp.status_code == 409


def test_list_credentials_never_returns_the_key(client):
    _create_credential(client)
    resp = client.get("/api/credentials", auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "account_key" not in body[0]


def test_delete_credential(client):
    created = _create_credential(client)
    resp = client.delete(f"/api/credentials/{created['id']}", auth=AUTH)
    assert resp.status_code == 204
    assert client.get("/api/credentials", auth=AUTH).json() == []


def test_delete_unknown_credential_404(client):
    resp = client.delete("/api/credentials/does-not-exist", auth=AUTH)
    assert resp.status_code == 404


def test_apply_credential_unknown_credential_404(client):
    enrolled = _enroll(client)
    resp = client.post(
        "/api/credentials/does-not-exist/apply", json={"node_id": enrolled["node_id"]}, auth=AUTH
    )
    assert resp.status_code == 404


def test_apply_credential_unknown_node_404(client):
    created = _create_credential(client)
    resp = client.post(f"/api/credentials/{created['id']}/apply", json={"node_id": "does-not-exist"}, auth=AUTH)
    assert resp.status_code == 404


def test_apply_credential_dispatches_attach_project_with_real_key(client, monkeypatch):
    """The stored key round-trips through encryption and actually reaches
    the node in plaintext, the same as if it had been typed into the
    dashboard's attach form directly -- only what's persisted/echoed back
    through the commands audit log is redacted."""
    enrolled = _enroll(client)
    node_id = enrolled["node_id"]
    created = _create_credential(client, account_key="supersecret123")

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(f"/api/credentials/{created['id']}/apply", json={"node_id": node_id}, auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["backend"] == "boinc"
    assert body["action"] == "attach_project"

    assert sent_frames[0]["payload"]["account_key"] == "supersecret123"
    assert sent_frames[0]["payload"]["project_url"] == "https://www.worldcommunitygrid.org/"

    # Never persisted/echoed back in plaintext, same redaction as a direct attach.
    assert body["payload"]["account_key"] != "supersecret123"


def test_apply_credential_updates_last_used_at(client, monkeypatch):
    enrolled = _enroll(client)
    node_id = enrolled["node_id"]
    created = _create_credential(client)
    assert created["last_used_at"] is None

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    async def fake_send_frame(wid, frame):
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    client.post(f"/api/credentials/{created['id']}/apply", json={"node_id": node_id}, auth=AUTH)

    refreshed = client.get("/api/credentials", auth=AUTH).json()[0]
    assert refreshed["last_used_at"] is not None


def test_apply_credential_to_offline_node_fails(client):
    enrolled = _enroll(client)
    created = _create_credential(client)
    resp = client.post(
        f"/api/credentials/{created['id']}/apply", json={"node_id": enrolled["node_id"]}, auth=AUTH
    )
    assert resp.status_code == 409


def test_apply_group_dispatches_to_online_members_and_skips_offline(client, monkeypatch):
    online_node = _enroll(client, "lab-1")
    offline_node = _enroll(client, "lab-2")
    other_group_node = _enroll(client, "library-1")
    client.put(f"/api/nodes/{online_node['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/nodes/{offline_node['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/nodes/{other_group_node['node_id']}/group", json={"group": "Library"}, auth=AUTH)
    created = _create_credential(client, account_key="supersecret123")

    monkeypatch.setattr(connections, "is_online", lambda wid: wid == online_node["node_id"])

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(f"/api/credentials/{created['id']}/apply-group/Lab 1", auth=AUTH)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2  # only Lab 1's two members, not the Library node

    by_node = {r["node_id"]: r for r in results}
    assert by_node[online_node["node_id"]]["online"] is True
    assert by_node[online_node["node_id"]]["status"] == "ok"
    assert by_node[offline_node["node_id"]]["online"] is False
    assert by_node[offline_node["node_id"]]["status"] == "skipped"

    # only the online node actually received the real key
    assert len(sent_frames) == 1
    assert sent_frames[0]["payload"]["account_key"] == "supersecret123"


def test_apply_group_unknown_group_returns_empty_list(client):
    created = _create_credential(client)
    resp = client.post(f"/api/credentials/{created['id']}/apply-group/does-not-exist", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_group_unknown_credential_404(client):
    resp = client.post("/api/credentials/does-not-exist/apply-group/Lab 1", auth=AUTH)
    assert resp.status_code == 404


def test_apply_all_dispatches_to_every_online_node(client, monkeypatch):
    w1 = _enroll(client, "w1")
    w2 = _enroll(client, "w2")
    created = _create_credential(client)

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    async def fake_send_frame(wid, frame):
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(f"/api/credentials/{created['id']}/apply-all", auth=AUTH)
    assert resp.status_code == 200
    results = resp.json()
    assert {r["node_id"] for r in results} == {w1["node_id"], w2["node_id"]}
    assert all(r["status"] == "ok" for r in results)


def test_apply_all_unknown_credential_404(client):
    resp = client.post("/api/credentials/does-not-exist/apply-all", auth=AUTH)
    assert resp.status_code == 404


def test_apply_all_with_no_nodes_returns_empty_list(client):
    created = _create_credential(client)
    resp = client.post(f"/api/credentials/{created['id']}/apply-all", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_group_all_offline_does_not_touch_last_used_at(client, monkeypatch):
    """No online nodes means no key was ever decrypted or dispatched --
    last_used_at should stay None, not get bumped for a no-op batch."""
    enrolled = _enroll(client)
    client.put(f"/api/nodes/{enrolled['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    created = _create_credential(client)

    monkeypatch.setattr(connections, "is_online", lambda wid: False)

    resp = client.post(f"/api/credentials/{created['id']}/apply-group/Lab 1", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "skipped"

    refreshed = client.get("/api/credentials", auth=AUTH).json()[0]
    assert refreshed["last_used_at"] is None


def test_create_credential_without_secret_key_configured_returns_500(client, monkeypatch):
    monkeypatch.delitem(os.environ, "GRIDKEEPER_SECRET_KEY", raising=False)
    resp = client.post(
        "/api/credentials",
        json={"name": "x", "project_url": "https://example.org/", "account_key": "abc"},
        auth=AUTH,
    )
    assert resp.status_code == 500
    assert "GRIDKEEPER_SECRET_KEY" in resp.json()["detail"]
