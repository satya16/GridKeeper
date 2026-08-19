from .conftest import ADMIN_PASSWORD, AUTH


def test_dashboard_requires_auth(client):
    resp = client.get("/")
    assert resp.status_code == 401


def test_dashboard_with_correct_password(client):
    resp = client.get("/", auth=AUTH)
    assert resp.status_code == 200
    assert "GridKeeper" in resp.text


def test_dashboard_with_wrong_password(client):
    resp = client.get("/", auth=("admin", "wrong-password"))
    assert resp.status_code == 401


def test_api_requires_auth(client):
    resp = client.get("/api/nodes")
    assert resp.status_code == 401


def test_any_username_accepted(client):
    resp = client.get("/", auth=("literally-anyone", ADMIN_PASSWORD))
    assert resp.status_code == 200
