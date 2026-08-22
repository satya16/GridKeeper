from app.metrics_store import store


def _enroll(auth_client, name: str = "node-1") -> dict:
    token = auth_client.post("/api/pairing-tokens", json={"label": ""}).json()["token"]
    resp = auth_client.post(
        "/api/enroll", json={"pairing_token": token, "name": name, "os_name": "linux", "backends": ["boinc"]}
    )
    assert resp.status_code == 200
    return resp.json()


def test_record_stores_estimated_watts():
    store.record("node-x", {"cpu_percent": 50.0, "ram_percent": 30.0, "temperature_c": 45.0, "estimated_watts": 95.0})
    point = store.history("node-x")[-1]
    assert point["estimated_watts"] == 95.0


def test_record_missing_estimated_watts_is_none():
    store.record("node-y", {"cpu_percent": 50.0})
    point = store.history("node-y")[-1]
    assert point["estimated_watts"] is None


def test_get_metrics_endpoint_includes_estimated_watts(auth_client):
    enrolled = _enroll(auth_client)
    store.record(enrolled["node_id"], {"cpu_percent": 20.0, "ram_percent": 10.0, "temperature_c": 40.0, "estimated_watts": 62.0})

    resp = auth_client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body[enrolled["node_id"]]["points"][-1]["estimated_watts"] == 62.0
