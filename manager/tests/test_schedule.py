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


def test_set_worker_schedule_persists(client):
    enrolled = _enroll(client, "sched-worker")
    resp = client.put(f"/api/workers/{enrolled['worker_id']}/schedule", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == DEFAULT_POLICY

    workers = client.get("/api/workers", auth=AUTH).json()
    assert workers[0]["schedule"] == DEFAULT_POLICY


def test_set_schedule_unknown_worker_404(client):
    resp = client.put("/api/workers/does-not-exist/schedule", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 404


def test_apply_schedule_to_all_workers(client):
    w1 = _enroll(client, "w1")
    w2 = _enroll(client, "w2")

    resp = client.post("/api/schedule/apply-all", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    affected = resp.json()
    assert sorted(affected) == sorted([w1["worker_id"], w2["worker_id"]])

    workers = client.get("/api/workers", auth=AUTH).json()
    assert all(w["schedule"] == DEFAULT_POLICY for w in workers)


def test_apply_schedule_with_no_workers_returns_empty_list(client):
    resp = client.post("/api/schedule/apply-all", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_schedule_to_group_only_affects_that_group(client):
    lab1a = _enroll(client, "lab1-a")
    lab1b = _enroll(client, "lab1-b")
    library = _enroll(client, "library-a")
    client.put(f"/api/workers/{lab1a['worker_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/workers/{lab1b['worker_id']}/group", json={"group": "Lab 1"}, auth=AUTH)
    client.put(f"/api/workers/{library['worker_id']}/group", json={"group": "Library"}, auth=AUTH)

    resp = client.post("/api/schedule/apply-group/Lab 1", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    affected = resp.json()
    assert sorted(affected) == sorted([lab1a["worker_id"], lab1b["worker_id"]])

    workers = {w["name"]: w for w in client.get("/api/workers", auth=AUTH).json()}
    assert workers["lab1-a"]["schedule"] == DEFAULT_POLICY
    assert workers["lab1-b"]["schedule"] == DEFAULT_POLICY
    assert workers["library-a"]["schedule"] is None


def test_apply_schedule_to_unknown_group_returns_empty_list(client):
    _enroll(client, "ungrouped-worker")
    resp = client.post("/api/schedule/apply-group/no-such-group", json=DEFAULT_POLICY, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_schedule_defaults_when_fields_omitted(client):
    enrolled = _enroll(client, "defaults-worker")
    resp = client.put(f"/api/workers/{enrolled['worker_id']}/schedule", json={}, auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["active_start_hour"] == 22
    assert body["active_end_hour"] == 6
