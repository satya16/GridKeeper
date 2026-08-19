from app.connections import connections

from .conftest import AUTH


def _enroll(client, name: str = "node-1") -> dict:
    token = client.post("/api/pairing-tokens", json={"label": ""}, auth=AUTH).json()["token"]
    resp = client.post(
        "/api/enroll", json={"pairing_token": token, "name": name, "os_name": "linux", "backends": ["boinc"]}
    )
    assert resp.status_code == 200
    return resp.json()


def test_list_nodes_empty(client):
    resp = client.get("/api/nodes", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_nodes_after_enroll(client):
    _enroll(client)
    nodes = client.get("/api/nodes", auth=AUTH).json()
    assert len(nodes) == 1
    assert nodes[0]["name"] == "node-1"
    assert nodes[0]["online"] is False
    assert nodes[0]["backends"] == ["boinc"]
    assert nodes[0]["group"] == ""


def test_set_node_group(client):
    enrolled = _enroll(client)
    resp = client.put(f"/api/nodes/{enrolled['node_id']}/group", json={"group": "Library"}, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"group": "Library"}

    nodes = client.get("/api/nodes", auth=AUTH).json()
    assert nodes[0]["group"] == "Library"


def test_set_node_group_unknown_node_404(client):
    resp = client.put("/api/nodes/does-not-exist/group", json={"group": "Library"}, auth=AUTH)
    assert resp.status_code == 404


def test_set_node_group_can_clear_it(client):
    enrolled = _enroll(client)
    client.put(f"/api/nodes/{enrolled['node_id']}/group", json={"group": "Library"}, auth=AUTH)
    resp = client.put(f"/api/nodes/{enrolled['node_id']}/group", json={"group": ""}, auth=AUTH)
    assert resp.status_code == 200
    nodes = client.get("/api/nodes", auth=AUTH).json()
    assert nodes[0]["group"] == ""


def test_list_groups_returns_distinct_nonempty_groups(client):
    w1 = _enroll(client, "w1")
    w2 = _enroll(client, "w2")
    w3 = _enroll(client, "w3")
    client.put(f"/api/nodes/{w1['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/nodes/{w2['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/nodes/{w3['node_id']}/group", json={"group": "Library"}, auth=AUTH)

    resp = client.get("/api/groups", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == ["Lab 1", "Library"]


def test_list_groups_excludes_ungrouped(client):
    _enroll(client)
    resp = client.get("/api/groups", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_node_not_found(client):
    resp = client.get("/api/nodes/does-not-exist", auth=AUTH)
    assert resp.status_code == 404


def test_issue_command_to_offline_node_fails(client):
    enrolled = _enroll(client)
    resp = client.post(
        f"/api/nodes/{enrolled['node_id']}/commands",
        json={"backend": "boinc", "action": "resume_all", "payload": {}},
        auth=AUTH,
    )
    assert resp.status_code == 409


def test_issue_command_to_unknown_node_404(client):
    resp = client.post(
        "/api/nodes/does-not-exist/commands",
        json={"backend": "boinc", "action": "resume_all", "payload": {}},
        auth=AUTH,
    )
    assert resp.status_code == 404


def test_issue_command_to_online_node_round_trips(client, monkeypatch):
    """No real WebSocket in a unit test -- simulate an online node that
    responds instantly, the same shape as main.py's command_result frame
    handling, and confirm the REST call gets the result back correctly."""
    enrolled = _enroll(client)
    node_id = enrolled["node_id"]

    monkeypatch.setattr(connections, "is_online", lambda wid: wid == node_id)

    async def fake_send_frame(wid, frame):
        assert wid == node_id
        assert frame["type"] == "command"
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"run_mode": "auto"}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(
        f"/api/nodes/{node_id}/commands",
        json={"backend": "boinc", "action": "resume_all", "payload": {}},
        auth=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["result"] == {"run_mode": "auto"}

    # And the command shows up in its own audit-log lookup.
    lookup = client.get(f"/api/nodes/{node_id}/commands/{body['id']}", auth=AUTH)
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "ok"


def test_issue_command_attach_project_redacts_account_key(client, monkeypatch):
    """account_key is a long-lived credential (the project account's
    authenticator), not a one-time pairing token -- must never land in
    the commands table, or its audit-log GET response, in plaintext. The
    node still needs the real value to actually attach, though."""
    enrolled = _enroll(client)
    node_id = enrolled["node_id"]

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"attached": True}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(
        f"/api/nodes/{node_id}/commands",
        json={
            "backend": "boinc",
            "action": "attach_project",
            "payload": {"project_url": "https://example.org/project/", "account_key": "supersecret123"},
        },
        auth=AUTH,
    )
    assert resp.status_code == 200

    # The node actually receives the real key -- it needs it to attach.
    assert sent_frames[0]["payload"]["account_key"] == "supersecret123"

    # But it's never persisted or echoed back in plaintext.
    body = resp.json()
    assert body["payload"]["account_key"] != "supersecret123"
    assert body["payload"]["project_url"] == "https://example.org/project/"

    lookup = client.get(f"/api/nodes/{node_id}/commands/{body['id']}", auth=AUTH)
    assert lookup.json()["payload"]["account_key"] != "supersecret123"


def test_issue_command_set_config_redacts_passkey(client, monkeypatch):
    """FAH passkey is a long-lived credential too -- same treatment as
    BOINC's account_key above."""
    enrolled = _enroll(client)
    node_id = enrolled["node_id"]

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    sent_frames = []

    async def fake_send_frame(wid, frame):
        sent_frames.append(frame)
        connections.resolve_pending(frame["command_id"], {"status": "ok", "result": {"updated": ["passkey"]}})
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(
        f"/api/nodes/{node_id}/commands",
        json={"backend": "fah", "action": "set_config", "payload": {"cause": "cancer", "passkey": "abcdef0123456789abcdef0123456789"}},
        auth=AUTH,
    )
    assert resp.status_code == 200

    assert sent_frames[0]["payload"]["passkey"] == "abcdef0123456789abcdef0123456789"

    body = resp.json()
    assert body["payload"]["passkey"] != "abcdef0123456789abcdef0123456789"
    assert body["payload"]["cause"] == "cancer"


def test_issue_command_node_error_result_still_returns_200(client, monkeypatch):
    """A command that reaches the node but fails there (e.g. boinccmd
    not installed) is a successful REST call reporting a failed command --
    not an HTTP error."""
    enrolled = _enroll(client)
    node_id = enrolled["node_id"]

    monkeypatch.setattr(connections, "is_online", lambda wid: True)

    async def fake_send_frame(wid, frame):
        connections.resolve_pending(
            frame["command_id"], {"status": "error", "result": {"error": "boinccmd not found on PATH"}}
        )
        return True

    monkeypatch.setattr(connections, "send_frame", fake_send_frame)

    resp = client.post(
        f"/api/nodes/{node_id}/commands",
        json={"backend": "boinc", "action": "resume_all", "payload": {}},
        auth=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "boinccmd not found" in body["result"]["error"]
