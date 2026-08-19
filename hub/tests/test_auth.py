from .conftest import ADMIN_PASSWORD, ADMIN_USERNAME


def test_dashboard_reachable_without_login(client):
    """Deliberately unauthenticated -- the login form itself lives in the
    React app, so the HTML/JS bundle has to load before anyone's logged
    in for that form to even render."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "GridKeeper" in resp.text


def test_api_requires_login(client):
    resp = client.get("/api/nodes")
    assert resp.status_code == 401


def test_session_check_requires_login(client):
    resp = client.get("/api/session")
    assert resp.status_code == 401


def test_login_with_correct_password(client):
    resp = client.post("/api/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "role": "admin"}
    assert "gridkeeper_session" in resp.cookies


def test_login_with_wrong_password(client):
    resp = client.post("/api/login", json={"username": ADMIN_USERNAME, "password": "not-it"})
    assert resp.status_code == 401
    assert "gridkeeper_session" not in resp.cookies


def test_login_with_unknown_username(client):
    resp = client.post("/api/login", json={"username": "nobody", "password": ADMIN_PASSWORD})
    assert resp.status_code == 401
    assert "gridkeeper_session" not in resp.cookies


def test_session_persists_across_requests_on_same_client(client):
    client.post("/api/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert client.get("/api/session").status_code == 200
    assert client.get("/api/nodes").status_code == 200


def test_session_reports_role(client):
    client.post("/api/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    resp = client.get("/api/session")
    assert resp.json()["role"] == "admin"


def test_logout_ends_the_session(client):
    client.post("/api/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert client.get("/api/session").status_code == 200

    resp = client.post("/api/logout")
    assert resp.status_code == 200

    assert client.get("/api/session").status_code == 401
    assert client.get("/api/nodes").status_code == 401


def test_bogus_session_cookie_is_rejected(client):
    client.cookies.set("gridkeeper_session", "not-a-real-token")
    resp = client.get("/api/nodes")
    assert resp.status_code == 401
