from .conftest import ADMIN_PASSWORD, ADMIN_USERNAME


def test_list_users_includes_bootstrap_admin(auth_client):
    resp = auth_client.get("/api/users")
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert usernames == [ADMIN_USERNAME]


def test_non_admin_cannot_list_users(auth_client, scoped_client):
    viewer = scoped_client(role="viewer")
    assert viewer.get("/api/users").status_code == 403


def test_create_user(auth_client):
    resp = auth_client.post(
        "/api/users", json={"username": "alice", "password": "hunter22", "role": "group_manager", "scope": "Lab 1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "alice"
    assert body["role"] == "group_manager"
    assert body["scope"] == "Lab 1"
    assert "password" not in body
    assert "password_hash" not in body

    login = auth_client.post("/api/login", json={"username": "alice", "password": "hunter22"})
    assert login.status_code == 200
    assert login.json()["role"] == "group_manager"


def test_create_user_duplicate_username_409(auth_client):
    auth_client.post("/api/users", json={"username": "bob", "password": "hunter22", "role": "viewer"})
    resp = auth_client.post("/api/users", json={"username": "bob", "password": "different", "role": "viewer"})
    assert resp.status_code == 409


def test_non_admin_cannot_create_user(auth_client, scoped_client):
    gm = scoped_client(role="group_manager", scope="Lab 1")
    resp = gm.post("/api/users", json={"username": "eve", "password": "hunter22", "role": "viewer"})
    assert resp.status_code == 403


def test_update_user_role_and_scope(auth_client):
    created = auth_client.post(
        "/api/users", json={"username": "carol", "password": "hunter22", "role": "viewer"}
    ).json()
    resp = auth_client.put(
        f"/api/users/{created['id']}", json={"role": "machine_manager", "scope": "node-123"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "machine_manager"
    assert resp.json()["scope"] == "node-123"


def test_update_user_password_lets_them_log_in_with_new_one(auth_client):
    created = auth_client.post(
        "/api/users", json={"username": "dave", "password": "old-password", "role": "viewer"}
    ).json()
    resp = auth_client.put(f"/api/users/{created['id']}", json={"password": "new-password"})
    assert resp.status_code == 200

    assert auth_client.post("/api/login", json={"username": "dave", "password": "new-password"}).status_code == 200
    assert auth_client.post("/api/login", json={"username": "dave", "password": "old-password"}).status_code == 401


def test_delete_user(auth_client):
    created = auth_client.post(
        "/api/users", json={"username": "erin", "password": "hunter22", "role": "viewer"}
    ).json()
    resp = auth_client.delete(f"/api/users/{created['id']}")
    assert resp.status_code == 204
    assert auth_client.post("/api/login", json={"username": "erin", "password": "hunter22"}).status_code == 401


def test_admin_cannot_delete_own_account(auth_client):
    me = auth_client.get("/api/me").json()
    resp = auth_client.delete(f"/api/users/{me['id']}")
    assert resp.status_code == 400


def test_get_me(auth_client):
    resp = auth_client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == ADMIN_USERNAME
    assert resp.json()["role"] == "admin"


def test_change_own_password(client):
    client.post("/api/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    resp = client.post("/api/me/password", json={"current_password": ADMIN_PASSWORD, "new_password": "new-hunter2"})
    assert resp.status_code == 200

    client.post("/api/logout")
    assert client.post("/api/login", json={"username": ADMIN_USERNAME, "password": "new-hunter2"}).status_code == 200
    assert client.post("/api/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).status_code == 401


def test_change_own_password_wrong_current_password_rejected(auth_client):
    resp = auth_client.post("/api/me/password", json={"current_password": "wrong", "new_password": "whatever"})
    assert resp.status_code == 401


def test_audit_log_records_actions(auth_client):
    auth_client.post("/api/users", json={"username": "frank", "password": "hunter22", "role": "viewer"})
    resp = auth_client.get("/api/audit-log")
    assert resp.status_code == 200
    entries = resp.json()
    assert any(e["action"] == "create_user" and e["target"] == "frank" for e in entries)
    assert all(e["username"] == ADMIN_USERNAME for e in entries)


def test_non_admin_cannot_view_audit_log(auth_client, scoped_client):
    viewer = scoped_client(role="viewer")
    assert viewer.get("/api/audit-log").status_code == 403
