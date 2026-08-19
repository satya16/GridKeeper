from .conftest import AUTH

DEFAULT_POLICY = {
    "enabled": True,
    "restrict_hours": True,
    "active_start_hour": 22,
    "active_end_hour": 6,
    "only_when_idle": False,
    "idle_threshold_minutes": 3,
}


def _enroll(client, name: str) -> dict:
    token = client.post("/api/pairing-tokens", json={"label": ""}, auth=AUTH).json()["token"]
    resp = client.post("/api/enroll", json={"pairing_token": token, "name": name, "os_name": "linux", "backends": []})
    return resp.json()


def test_set_node_schedule_persists(client):
    enrolled = _enroll(client, "sched-node")
    resp = client.put(f"/api/nodes/{enrolled['node_id']}/schedule", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == DEFAULT_POLICY

    nodes = client.get("/api/nodes", auth=AUTH).json()
    assert nodes[0]["schedule"] == DEFAULT_POLICY


def test_set_schedule_unknown_node_404(client):
    resp = client.put("/api/nodes/does-not-exist/schedule", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 404


def test_apply_schedule_to_all_nodes(client):
    w1 = _enroll(client, "w1")
    w2 = _enroll(client, "w2")

    resp = client.post("/api/schedule/apply-all", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    affected = resp.json()
    assert sorted(affected) == sorted([w1["node_id"], w2["node_id"]])

    nodes = client.get("/api/nodes", auth=AUTH).json()
    assert all(w["schedule"] == DEFAULT_POLICY for w in nodes)


def test_apply_schedule_with_no_nodes_returns_empty_list(client):
    resp = client.post("/api/schedule/apply-all", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_schedule_to_group_only_affects_that_group(client):
    lab1a = _enroll(client, "lab1-a")
    lab1b = _enroll(client, "lab1-b")
    library = _enroll(client, "library-a")
    client.put(f"/api/nodes/{lab1a['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/nodes/{lab1b['node_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/nodes/{library['node_id']}/group", json={"group": "Library"}, auth=AUTH)

    resp = client.post("/api/schedule/apply-group/Lab 1", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    affected = resp.json()
    assert sorted(affected) == sorted([lab1a["node_id"], lab1b["node_id"]])

    nodes = {w["name"]: w for w in client.get("/api/nodes", auth=AUTH).json()}
    assert nodes["lab1-a"]["schedule"] == DEFAULT_POLICY
    assert nodes["lab1-b"]["schedule"] == DEFAULT_POLICY
    assert nodes["library-a"]["schedule"] is None


def test_apply_schedule_to_unknown_group_returns_empty_list(client):
    _enroll(client, "ungrouped-node")
    resp = client.post("/api/schedule/apply-group/no-such-group", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_schedule_defaults_when_fields_omitted(client):
    enrolled = _enroll(client, "defaults-node")
    resp = client.put(f"/api/nodes/{enrolled['node_id']}/schedule", json={}, auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["active_start_hour"] == 22
    assert body["active_end_hour"] == 6
