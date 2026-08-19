import os

from app.connections import connections



def _enroll(auth_client, name: str = "node-1") -> dict:
    token = auth_client.post("/api/pairing-tokens", json={"label": ""}).json()["token"]
    resp = auth_client.post(
        "/api/enroll", json={"pairing_token": token, "name": name, "os_name": "linux", "backends": ["boinc"]}
    )
    assert resp.status_code == 200
    return resp.json()


def _create_credential(auth_client, name: str = "wcg-lab-account", account_key: str = "supersecret123") -> dict:
    resp = auth_client.post(
        "/api/credentials",
        json={"name": name, "project_url": "https://www.worldcommunitygrid.org/", "account_key": account_key},
    )
    assert resp.status_code == 200
    return resp.json()


def test_create_credential_never_returns_the_key(auth_client):
    body = _create_credential(auth_client)
    assert body["name"] == "wcg-lab-account"
    assert body["project_url"] == "https://www.worldcommunitygrid.org/"
    assert "account_key" not in body
    assert "key" not in body


def test_create_credential_rejects_duplicate_name(auth_client):
    _create_credential(auth_client)
    resp = auth_client.post(
        "/api/credentials",
        json={"name": "wcg-lab-account", "project_url": "https://example.org/", "account_key": "other"},
    )
    assert resp.status_code == 409


def test_list_credentials_never_returns_the_key(auth_client):
    _create_credential(auth_client)
    resp = auth_client.get("/api/credentials")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "account_key" not in body[0]


def test_delete_credential(auth_client):
    created = _create_credential(auth_client)
    resp = auth_client.delete(f"/api/credentials/{created['id']}")
    assert resp.status_code == 204
    assert auth_client.get("/api/credentials").json() == []


def test_delete_unknown_credential_404(auth_client):
    resp = auth_client.delete("/api/credentials/does-not-exist")
    assert resp.status_code == 404


def test_apply_credential_unknown_credential_404(auth_client):
    enrolled = _enroll(auth_client)
    resp = auth_client.post(
        "/api/credentials/does-not-exist/apply", json={"node_id": enrolled["node_id"]}
    )
    assert resp.status_code == 404


def test_apply_credential_unknown_node_404(auth_client):
    created = _create_credential(auth_client)
    resp = auth_client.post(f"/api/credentials/{created['id']}/apply", json={"node_id": "does-not-exist"})
    assert resp.status_code == 404


def test_apply_credential_dispatches_attach_project_with_real_key(auth_client, monkeypatch):
    """The stored key round-trips through encryption and actually reaches
    the node in plaintext, the same as if it had been typed into the
    dashboard's attach form directly -- only what's persisted/echoed back
    through the commands audit log is redacted."""
    enrolled = _enroll(auth_client)
    node_id = enrolled["node_id"]
    created = _create_credential(auth_client, account_key="supersecret123")

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = auth_client.post(f"/api/credentials/{created['id']}/apply", json={"node_id": node_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["backend"] == "boinc"
    assert body["action"] == "attach_project"

    assert sent_frames[0]["payload"]["account_key"] == "supersecret123"
    assert sent_frames[0]["payload"]["project_url"] == "https://www.worldcommunitygrid.org/"

    # Never persisted/echoed back in plaintext, same redaction as a direct attach.
    assert body["payload"]["account_key"] != "supersecret123"


def test_apply_credential_updates_last_used_at(auth_client, monkeypatch):
    enrolled = _enroll(auth_client)
    node_id = enrolled["node_id"]
    created = _create_credential(auth_client)
    assert created["last_used_at"] is None

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    async def fake_send_frame(wid, frame):
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    auth_client.post(f"/api/credentials/{created['id']}/apply", json={"node_id": node_id})

    refreshed = auth_client.get("/api/credentials").json()[0]
    assert refreshed["last_used_at"] is not None


def test_apply_credential_to_offline_node_fails(auth_client):
    enrolled = _enroll(auth_client)
    created = _create_credential(auth_client)
    resp = auth_client.post(
        f"/api/credentials/{created['id']}/apply", json={"node_id": enrolled["node_id"]}
    )
    assert resp.status_code == 409


def test_apply_group_dispatches_to_online_members_and_skips_offline(auth_client, monkeypatch):
    online_node = _enroll(auth_client, "lab-1")
    offline_node = _enroll(auth_client, "lab-2")
    other_group_node = _enroll(auth_client, "library-1")
    auth_client.put(f"/api/nodes/{online_node['node_id']}/group", json={"group": "Lab 1"})
    auth_client.put(f"/api/nodes/{offline_node['node_id']}/group", json={"group": "Lab 1"})
    auth_client.put(f"/api/nodes/{other_group_node['node_id']}/group", json={"group": "Library"})
    created = _create_credential(auth_client, account_key="supersecret123")

    monkeypatch.setattr(connections, "is_online", lambda wid: wid == online_node["node_id"])

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = auth_client.post(f"/api/credentials/{created['id']}/apply-group/Lab 1")
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


def test_apply_group_unknown_group_returns_empty_list(auth_client):
    created = _create_credential(auth_client)
    resp = auth_client.post(f"/api/credentials/{created['id']}/apply-group/does-not-exist")
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_group_unknown_credential_404(auth_client):
    resp = auth_client.post("/api/credentials/does-not-exist/apply-group/Lab 1")
    assert resp.status_code == 404


def test_apply_all_dispatches_to_every_online_node(auth_client, monkeypatch):
    w1 = _enroll(auth_client, "w1")
    w2 = _enroll(auth_client, "w2")
    created = _create_credential(auth_client)

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    async def fake_send_frame(wid, frame):
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = auth_client.post(f"/api/credentials/{created['id']}/apply-all")
    assert resp.status_code == 200
    results = resp.json()
    assert {r["node_id"] for r in results} == {w1["node_id"], w2["node_id"]}
    assert all(r["status"] == "ok" for r in results)


def test_apply_all_unknown_credential_404(auth_client):
    resp = auth_client.post("/api/credentials/does-not-exist/apply-all")
    assert resp.status_code == 404


def test_apply_all_with_no_nodes_returns_empty_list(auth_client):
    created = _create_credential(auth_client)
    resp = auth_client.post(f"/api/credentials/{created['id']}/apply-all")
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_group_all_offline_does_not_touch_last_used_at(auth_client, monkeypatch):
    """No online nodes means no key was ever decrypted or dispatched --
    last_used_at should stay None, not get bumped for a no-op batch."""
    enrolled = _enroll(auth_client)
    auth_client.put(f"/api/nodes/{enrolled['node_id']}/group", json={"group": "Lab 1"})
    created = _create_credential(auth_client)

    monkeypatch.setattr(connections, "is_online", lambda wid: False)

    resp = auth_client.post(f"/api/credentials/{created['id']}/apply-group/Lab 1")
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "skipped"

    refreshed = auth_client.get("/api/credentials").json()[0]
    assert refreshed["last_used_at"] is None


def test_create_credential_without_secret_key_configured_returns_500(auth_client, monkeypatch):
    monkeypatch.delitem(os.environ, "GRIDKEEPER_SECRET_KEY", raising=False)
    resp = auth_client.post(
        "/api/credentials",
        json={"name": "x", "project_url": "https://example.org/", "account_key": "abc"},
    )
    assert resp.status_code == 500
    assert "GRIDKEEPER_SECRET_KEY" in resp.json()["detail"]


def test_non_admin_cannot_create_credential(auth_client, scoped_client):
    gm = scoped_client(role="group_manager", scope="Lab 1")
    resp = gm.post(
        "/api/credentials",
        json={"name": "x", "project_url": "https://example.org/", "account_key": "abc"},
    )
    assert resp.status_code == 403


def test_non_admin_cannot_delete_credential(auth_client, scoped_client):
    created = _create_credential(auth_client)
    viewer = scoped_client(role="viewer")
    assert viewer.delete(f"/api/credentials/{created['id']}").status_code == 403


def test_non_admin_can_list_credentials(auth_client, scoped_client):
    _create_credential(auth_client)
    viewer = scoped_client(role="viewer")
    resp = viewer.get("/api/credentials")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_machine_manager_can_apply_credential_to_own_node(auth_client, monkeypatch):
    enrolled = _enroll(auth_client)
    created = _create_credential(auth_client)
    from .conftest import make_scoped_client

    mm = make_scoped_client(auth_client, role="machine_manager", scope=enrolled["node_id"])

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    async def fake_send_frame(wid, frame):
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = mm.post(f"/api/credentials/{created['id']}/apply", json={"node_id": enrolled["node_id"]})
    assert resp.status_code == 200


def test_machine_manager_cannot_apply_credential_to_other_node(auth_client):
    mine = _enroll(auth_client, "mm-mine")
    other = _enroll(auth_client, "mm-other")
    created = _create_credential(auth_client)
    from .conftest import make_scoped_client

    mm = make_scoped_client(auth_client, role="machine_manager", scope=mine["node_id"])
    resp = mm.post(f"/api/credentials/{created['id']}/apply", json={"node_id": other["node_id"]})
    assert resp.status_code == 403


def test_group_manager_can_apply_to_own_group_not_others(auth_client):
    w1 = _enroll(auth_client, "gc1")
    w2 = _enroll(auth_client, "gc2")
    auth_client.put(f"/api/nodes/{w1['node_id']}/group", json={"group": "Lab 1"})
    auth_client.put(f"/api/nodes/{w2['node_id']}/group", json={"group": "Lab 2"})
    created = _create_credential(auth_client)
    from .conftest import make_scoped_client

    gm = make_scoped_client(auth_client, role="group_manager", scope="Lab 1")
    assert gm.post(f"/api/credentials/{created['id']}/apply-group/Lab 1").status_code == 200
    assert gm.post(f"/api/credentials/{created['id']}/apply-group/Lab 2").status_code == 403


def test_machine_manager_cannot_apply_to_group(auth_client):
    created = _create_credential(auth_client)
    from .conftest import make_scoped_client

    mm = make_scoped_client(auth_client, role="machine_manager", scope="some-node-id")
    assert mm.post(f"/api/credentials/{created['id']}/apply-group/Lab 1").status_code == 403


def test_non_admin_cannot_apply_to_all(auth_client, scoped_client):
    created = _create_credential(auth_client)
    gm = scoped_client(role="group_manager", scope="Lab 1")
    assert gm.post(f"/api/credentials/{created['id']}/apply-all").status_code == 403
