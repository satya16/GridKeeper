def _mint_token(auth_client, label: str = "") -> str:
    resp = auth_client.post("/api/pairing-tokens", json={"label": label})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_create_pairing_token(auth_client):
    resp = auth_client.post("/api/pairing-tokens", json={"label": "test"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "test"
    assert len(body["token"]) > 10


def test_create_pairing_token_requires_auth(client):
    resp = client.post("/api/pairing-tokens", json={"label": "test"})
    assert resp.status_code == 401


def test_enroll_with_valid_token(auth_client):
    token = _mint_token(auth_client)
    resp = auth_client.post(
        "/api/enroll",
        json={"pairing_token": token, "name": "node-1", "os_name": "linux", "backends": ["boinc"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "node_id" in body
    assert "bearer_token" in body
    # Enroll itself needs no admin auth -- it's how a brand-new node
    # bootstraps trust in the first place.


def test_enroll_with_used_token_fails(auth_client):
    token = _mint_token(auth_client)
    auth_client.post("/api/enroll", json={"pairing_token": token, "name": "node-a", "os_name": "linux", "backends": []})
    resp = auth_client.post(
        "/api/enroll", json={"pairing_token": token, "name": "node-b", "os_name": "linux", "backends": []}
    )
    assert resp.status_code == 400


def test_enroll_with_unknown_token_fails(auth_client):
    resp = auth_client.post(
        "/api/enroll", json={"pairing_token": "does-not-exist", "name": "x", "os_name": "linux", "backends": []}
    )
    assert resp.status_code == 400


def test_enroll_inherits_group_from_pairing_token(auth_client):
    resp = auth_client.post("/api/pairing-tokens", json={"label": "", "group": "Lab 1"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    assert resp.json()["group"] == "Lab 1"

    auth_client.post(
        "/api/enroll", json={"pairing_token": token, "name": "lab1-machine", "os_name": "linux", "backends": []}
    )
    nodes = auth_client.get("/api/nodes").json()
    assert nodes[0]["group"] == "Lab 1"


def test_enroll_with_token_with_no_group_leaves_node_ungrouped(auth_client):
    token = _mint_token(auth_client)
    auth_client.post("/api/enroll", json={"pairing_token": token, "name": "ungrouped", "os_name": "linux", "backends": []})
    nodes = auth_client.get("/api/nodes").json()
    assert nodes[0]["group"] == ""


def test_enroll_duplicate_name_fails(auth_client):
    t1 = _mint_token(auth_client)
    auth_client.post("/api/enroll", json={"pairing_token": t1, "name": "dup-node", "os_name": "linux", "backends": []})
    t2 = _mint_token(auth_client)
    resp = auth_client.post(
        "/api/enroll", json={"pairing_token": t2, "name": "dup-node", "os_name": "linux", "backends": []}
    )
    assert resp.status_code == 400
    # The unused second token should still be available for a retry with
    # a different name -- enroll failing shouldn't burn the token.
    resp2 = auth_client.post(
        "/api/enroll", json={"pairing_token": t2, "name": "dup-node-2", "os_name": "linux", "backends": []}
    )
    assert resp2.status_code == 200


def test_group_manager_can_mint_token_for_own_group(auth_client, scoped_client):
    gm = scoped_client(role="group_manager", scope="Lab 1")
    resp = gm.post("/api/pairing-tokens", json={"label": "", "group": "Lab 1"})
    assert resp.status_code == 200


def test_group_manager_cannot_mint_token_for_other_group(auth_client, scoped_client):
    gm = scoped_client(role="group_manager", scope="Lab 1")
    resp = gm.post("/api/pairing-tokens", json={"label": "", "group": "Lab 2"})
    assert resp.status_code == 403


def test_group_manager_cannot_mint_ungrouped_token(auth_client, scoped_client):
    gm = scoped_client(role="group_manager", scope="Lab 1")
    resp = gm.post("/api/pairing-tokens", json={"label": ""})
    assert resp.status_code == 403


def test_machine_manager_cannot_mint_pairing_token(auth_client, scoped_client):
    mm = scoped_client(role="machine_manager", scope="some-node-id")
    resp = mm.post("/api/pairing-tokens", json={"label": ""})
    assert resp.status_code == 403


def test_viewer_cannot_mint_pairing_token(auth_client, scoped_client):
    viewer = scoped_client(role="viewer")
    resp = viewer.post("/api/pairing-tokens", json={"label": ""})
    assert resp.status_code == 403
