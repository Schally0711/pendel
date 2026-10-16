from fastapi.testclient import TestClient

from pendel.setup import setup_code

from .conftest import PASSWORD


def test_setup_only_once(client):
    assert client.get("/api/setup").json() == {"needed": True}
    body = {"email": "a@example.org", "password": PASSWORD, "display_name": "A"}
    # the first account needs the one-time code from the server log
    assert client.post("/api/setup", json=body).status_code == 403
    assert client.post("/api/setup", json=body | {"setup_code": "AAAA-BBBB-CCCC"}).status_code == 403
    body["setup_code"] = setup_code().lower()  # case does not matter
    assert client.post("/api/setup", json=body).status_code == 201
    assert client.get("/api/setup").json() == {"needed": False}
    assert client.post("/api/setup", json=body | {"email": "b@example.org"}).status_code == 409


def test_setup_creates_admin_with_defaults(admin):
    me = admin.get("/api/me").json()
    assert me["is_admin"] and me["email"] == "admin@example.org" and me["subdivision"] == "NW"
    (model,) = admin.get("/api/work-models").json()
    assert model["target_mon"] == 480 and model["target_sat"] == 0
    assert [p["kind"] for p in admin.get("/api/places").json()] == ["home", "office"]


def test_login_logout(admin):
    admin.post("/api/auth/logout")
    assert admin.get("/api/me").status_code == 401
    bad = admin.post("/api/auth/login", json={"email": "admin@example.org", "password": "wrong"})
    assert bad.status_code == 401
    ok = admin.post("/api/auth/login", json={"email": " ADMIN@example.org", "password": PASSWORD})
    assert ok.status_code == 200
    assert admin.get("/api/me").status_code == 200


def test_login_rate_limit(admin):
    admin.post("/api/auth/logout")
    for _ in range(10):
        admin.post("/api/auth/login", json={"email": "x@example.org", "password": "nope"})
    r = admin.post("/api/auth/login", json={"email": "admin@example.org", "password": PASSWORD})
    assert r.status_code == 429


def test_csrf_header_required(admin):
    r = admin.post("/api/auth/logout", headers={"X-Requested-With": ""})
    assert r.status_code == 403


def test_short_password_rejected(client):
    r = client.post("/api/setup", json={"email": "a@example.org", "password": "short", "display_name": "A"})
    assert r.status_code == 422


def test_invitation_flow(admin):
    created = admin.post("/api/admin/invitations", json={"note": "Max"}).json()
    token = created["token"]

    guest = TestClient(admin.app, headers={"X-Requested-With": "pendel"})
    assert guest.get(f"/api/invitations/{token}").json() == {"valid": True, "note": "Max"}
    assert guest.post("/api/admin/invitations", json={}).status_code == 401
    body = {"email": "max@example.org", "password": PASSWORD, "display_name": "Max", "locale": "en"}
    r = guest.post(f"/api/invitations/{token}/accept", json=body)
    assert r.status_code == 201 and not r.json()["is_admin"]
    assert [p["name"] for p in guest.get("/api/places").json()] == ["Home", "Office"]

    # used up
    assert guest.get(f"/api/invitations/{token}").json()["valid"] is False
    again = guest.post(f"/api/invitations/{token}/accept", json=body | {"email": "other@example.org"})
    assert again.status_code == 404
    # no admin rights
    assert guest.get("/api/admin/users").status_code == 403
    assert len(admin.get("/api/admin/users").json()) == 2


def test_update_me(admin):
    assert admin.patch("/api/me", json={"subdivision": "BY", "locale": "en"}).json()["subdivision"] == "BY"
    assert admin.patch("/api/me", json={"subdivision": "XX"}).status_code == 422
    assert admin.patch("/api/me", json={"timezone": "Mars/Base"}).status_code == 422


def test_change_password(admin):
    wrong = admin.post("/api/me/password", json={"current_password": "x", "new_password": "another password"})
    assert wrong.status_code == 400
    ok = admin.post(
        "/api/me/password", json={"current_password": PASSWORD, "new_password": "another password"}
    )
    assert ok.status_code == 204


def test_instance_public_url(admin, monkeypatch):
    assert admin.get("/api/instance").json()["public_url"] is None
    monkeypatch.setenv("PENDEL_PUBLIC_URL", "https://env.example.org")
    from pendel.config import get_settings

    get_settings.cache_clear()
    assert admin.get("/api/instance").json()["public_url"] == "https://env.example.org"
    r = admin.put("/api/admin/instance", json={"public_url": "https://pendel.example.com/"})
    assert r.json()["public_url"] == "https://pendel.example.com"  # stored value wins, no trailing slash
    assert admin.put("/api/admin/instance", json={"public_url": "pendel.example.com"}).status_code == 422
    assert admin.put("/api/admin/instance", json={"public_url": "https://x.org/sub"}).status_code == 422
    assert (
        admin.put("/api/admin/instance", json={"public_url": ""}).json()["public_url"]
        == "https://env.example.org"
    )
    created = admin.post("/api/calendar/token").json()
    assert created["public_url"] == "https://env.example.org"
    get_settings.cache_clear()


def test_setup_code_from_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDEL_SETUP_TOKEN", "my-install-token")
    from pendel import setup
    from pendel.config import get_settings

    get_settings.cache_clear()
    setup.reset()
    try:
        assert setup.check_setup_code("MY-INSTALL-TOKEN") and not setup.check_setup_code("")
    finally:
        get_settings.cache_clear()
        setup.reset()
