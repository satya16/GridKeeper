import pytest

from app.discovery import registry


@pytest.fixture(autouse=True)
def _clear_discovery_registry():
    registry._nodes.clear()
    yield
    registry._nodes.clear()


def _seed_discovered(discovery_id: str, *, addr: str = "10.0.0.5", port: int = 9001, hostname: str = "machine-1", backends=None) -> None:
    registry._nodes[discovery_id] = {
        "discovery_id": discovery_id,
        "hostname": hostname,
        "backends": backends or ["boinc"],
        "addresses": [addr],
        "port": port,
    }


class _FakeResponse:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self) -> dict:
        return self._data


def _install_fake_node_http(monkeypatch, valid_codes: dict[str, str]):
    """valid_codes: "{addr}:{port}" -> the code that machine will accept,
    mirroring the real node's local pairing HTTP listener (see
    node/grid_node/pairing.py) without needing a real one running."""

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url: str, json: dict | None = None):
            if url.endswith("/pair-complete"):
                return _FakeResponse(200, {})
            base = url[len("http://") :].split("/pair", 1)[0]
            if valid_codes.get(base) == (json or {}).get("code"):
                return _FakeResponse(200, {"name": "", "os_name": "linux", "backends": ["boinc"]})
            return _FakeResponse(400, {})

    monkeypatch.setattr("app.api.discovery.httpx.AsyncClient", FakeAsyncClient)


def test_pair_discovered_success(auth_client, monkeypatch):
    _seed_discovered("disc-1", addr="10.0.0.5", port=9001)
    _install_fake_node_http(monkeypatch, {"10.0.0.5:9001": "482913"})

    resp = auth_client.post("/api/discovery/disc-1/pair", json={"code": "482913", "name": "lab-pc-1", "group": "Lab 1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "lab-pc-1"

    nodes = auth_client.get("/api/nodes").json()
    assert nodes[0]["name"] == "lab-pc-1"
    assert nodes[0]["group"] == "Lab 1"


def test_pair_discovered_wrong_code_rejected(auth_client, monkeypatch):
    _seed_discovered("disc-1", addr="10.0.0.5", port=9001)
    _install_fake_node_http(monkeypatch, {"10.0.0.5:9001": "482913"})

    resp = auth_client.post("/api/discovery/disc-1/pair", json={"code": "000000"})
    assert resp.status_code == 400
    assert auth_client.get("/api/nodes").json() == []


def test_pair_discovered_unknown_discovery_id_404(auth_client, monkeypatch):
    _install_fake_node_http(monkeypatch, {})
    resp = auth_client.post("/api/discovery/does-not-exist/pair", json={"code": "482913"})
    assert resp.status_code == 404


def test_pair_batch_tolerates_partial_failure(auth_client, monkeypatch):
    _seed_discovered("disc-1", addr="10.0.0.5", port=9001, hostname="machine-1")
    _seed_discovered("disc-2", addr="10.0.0.6", port=9002, hostname="machine-2")
    _install_fake_node_http(monkeypatch, {"10.0.0.5:9001": "111111", "10.0.0.6:9002": "222222"})

    resp = auth_client.post(
        "/api/discovery/pair-batch",
        json={
            "pairs": [
                {"discovery_id": "disc-1", "code": "111111", "name": "", "group": "Lab 1"},
                {"discovery_id": "disc-2", "code": "wrong-code", "name": "", "group": "Lab 1"},
            ]
        },
    )
    assert resp.status_code == 200
    results = resp.json()
    by_id = {r["discovery_id"]: r for r in results}
    assert by_id["disc-1"]["ok"] is True
    assert by_id["disc-1"]["name"] == "machine-1"
    assert by_id["disc-2"]["ok"] is False
    assert by_id["disc-2"]["error"]

    # The failure of disc-2 must not roll back disc-1's already-committed pairing.
    nodes = auth_client.get("/api/nodes").json()
    assert len(nodes) == 1
    assert nodes[0]["name"] == "machine-1"


def test_pair_batch_applies_schedule_to_all_successful(auth_client, monkeypatch):
    _seed_discovered("disc-1", addr="10.0.0.5", port=9001, hostname="machine-1")
    _install_fake_node_http(monkeypatch, {"10.0.0.5:9001": "111111"})

    resp = auth_client.post(
        "/api/discovery/pair-batch",
        json={
            "pairs": [{"discovery_id": "disc-1", "code": "111111", "name": "", "group": ""}],
            "schedule": {"enabled": True, "restrict_hours": True, "active_start_hour": 22, "active_end_hour": 6},
        },
    )
    assert resp.status_code == 200
    node = auth_client.get("/api/nodes").json()[0]
    assert node["schedule"]["enabled"] is True
    assert node["schedule"]["active_start_hour"] == 22


def test_pair_batch_group_manager_scoped_to_own_group(auth_client, scoped_client, monkeypatch):
    _seed_discovered("disc-1", addr="10.0.0.5", port=9001, hostname="machine-1")
    _install_fake_node_http(monkeypatch, {"10.0.0.5:9001": "111111"})
    gm = scoped_client(role="group_manager", scope="Lab 1")

    resp = gm.post(
        "/api/discovery/pair-batch",
        json={"pairs": [{"discovery_id": "disc-1", "code": "111111", "name": "", "group": "Lab 2"}]},
    )
    assert resp.status_code == 403


def test_pair_batch_requires_discovery_access(auth_client, scoped_client):
    viewer = scoped_client(role="viewer")
    resp = viewer.post("/api/discovery/pair-batch", json={"pairs": []})
    assert resp.status_code == 403
