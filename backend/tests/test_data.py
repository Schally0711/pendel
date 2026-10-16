"""Password reset links, personal export, deleting the own account, instance backup and restore."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from pendel.setup import setup_code

from .conftest import PASSWORD

EMAIL = "admin@example.org"


def invite_friend(admin) -> tuple[TestClient, int]:
    token = admin.post("/api/admin/invitations", json={}).json()["token"]
    friend = TestClient(admin.app, headers={"X-Requested-With": "pendel"})
    body = {"email": "friend@example.org", "password": PASSWORD, "display_name": "Friend"}
    assert friend.post(f"/api/invitations/{token}/accept", json=body).status_code == 201
    return friend, friend.get("/api/me").json()["id"]


def test_password_reset_link(admin):
    friend, fid = invite_friend(admin)
    first = admin.post(f"/api/admin/users/{fid}/password-reset").json()["token"]
    token = admin.post(f"/api/admin/users/{fid}/password-reset").json()["token"]  # replaces the first
    assert friend.get(f"/api/password-reset/{first}").json()["valid"] is False
    assert friend.get(f"/api/password-reset/{token}").json() == {"valid": True, "display_name": "Friend"}

    anon = TestClient(admin.app, headers={"X-Requested-With": "pendel"})
    assert anon.post(f"/api/password-reset/{token}", json={"new_password": "short"}).status_code == 422
    assert (
        anon.post(f"/api/password-reset/{token}", json={"new_password": "brand new password"}).status_code
        == 204
    )
    assert (
        anon.post(f"/api/password-reset/{token}", json={"new_password": "another password"}).status_code
        == 404
    )
    assert friend.get("/api/me").status_code == 401  # signed out everywhere
    login = {"email": "friend@example.org", "password": "brand new password"}
    assert anon.post("/api/auth/login", json=login).status_code == 200
    # only admins create links
    assert anon.post(f"/api/admin/users/{fid}/password-reset").status_code == 403


def test_personal_export_has_data_but_no_secrets(admin):
    admin.post("/api/adjustments", json={"day": "2026-10-01", "minutes": 90, "note": "Start"})
    admin.post("/api/tokens", json={"name": "HA"})
    r = admin.get("/api/me/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["format"] == "pendel-user-export" and data["user"]["email"] == EMAIL
    assert data["balance_adjustments"][0]["minutes"] == 90
    assert [t["name"] for t in data["api_tokens"]] == ["HA"]
    text = json.dumps(data)
    assert "password_hash" not in text and "token_hash" not in text and "argon2" not in text


def test_delete_own_account(admin):
    friend, fid = invite_friend(admin)
    assert friend.post("/api/me/delete", json={"password": "wrong"}).status_code == 400
    assert friend.post("/api/me/delete", json={"password": PASSWORD}).status_code == 204
    assert friend.get("/api/me").status_code == 401
    assert [u["id"] for u in admin.get("/api/admin/users").json()] == [1]


def test_last_admin_cannot_leave_others_behind(admin):
    invite_friend(admin)
    r = admin.post("/api/me/delete", json={"password": PASSWORD})
    assert (r.status_code, r.json()["detail"]) == (409, "last_admin")


def test_backup_and_restore(admin):
    admin.post("/api/adjustments", json={"day": "2026-10-01", "minutes": 60, "note": "before"})
    r = admin.get("/api/admin/backup")
    assert r.status_code == 200 and r.content.startswith(b"SQLite format 3")
    backup = r.content
    admin.post("/api/adjustments", json={"day": "2026-10-02", "minutes": 30, "note": "after"})

    headers = {"Content-Type": "application/octet-stream"}
    r = admin.post("/api/admin/restore", content=backup, headers=headers | {"X-Confirm-Password": "wrong"})
    assert r.status_code == 400
    r = admin.post("/api/admin/restore", content=backup, headers=headers | {"X-Confirm-Password": PASSWORD})
    assert r.status_code == 204, r.text
    assert [a["note"] for a in admin.get("/api/adjustments").json()] == ["before"]


@pytest.mark.parametrize(
    ("content", "detail"),
    [(b"not a database", "backup_not_pendel"), (b"", "backup_not_pendel")],
)
def test_restore_rejects_garbage(admin, content, detail):
    headers = {"Content-Type": "application/octet-stream", "X-Confirm-Password": PASSWORD}
    r = admin.post("/api/admin/restore", content=content, headers=headers)
    assert (r.status_code, r.json()["detail"]) == (400, detail)
    assert admin.get("/api/me").status_code == 200  # nothing was replaced


def test_restore_rejects_unknown_schema(admin, tmp_path):
    backup = admin.get("/api/admin/backup").content
    path = tmp_path / "future.db"
    path.write_bytes(backup)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE alembic_version SET version_num = 'ffffffffffff'")
    conn.commit()
    conn.close()  # checkpoints the WAL into the file
    headers = {"Content-Type": "application/octet-stream", "X-Confirm-Password": PASSWORD}
    r = admin.post("/api/admin/restore", content=path.read_bytes(), headers=headers)
    assert (r.status_code, r.json()["detail"]) == (400, "backup_too_new")


def test_restore_on_fresh_instance(admin, tmp_path, monkeypatch):
    """Back up one instance, start a fresh one and restore it from the setup page."""
    admin.post("/api/adjustments", json={"day": "2026-10-01", "minutes": 45, "note": "old instance"})
    backup = admin.get("/api/admin/backup").content

    from pendel import setup
    from pendel.config import get_settings
    from pendel.db import get_engine, get_sessionmaker
    from pendel.main import create_app

    get_engine().dispose()
    fresh = tmp_path / "fresh"
    monkeypatch.setenv("PENDEL_DATA_DIR", str(fresh))
    for cache in (get_settings, get_engine, get_sessionmaker):
        cache.cache_clear()
    setup.reset()
    with TestClient(create_app(), headers={"X-Requested-With": "pendel"}) as c:
        assert c.get("/api/setup").json() == {"needed": True}
        headers = {"Content-Type": "application/octet-stream"}
        r = c.post("/api/setup/restore", content=backup, headers=headers | {"X-Setup-Code": "wrong"})
        assert r.status_code == 403
        r = c.post("/api/setup/restore", content=backup, headers=headers | {"X-Setup-Code": setup_code()})
        assert r.status_code == 204, r.text
        assert c.get("/api/setup").json() == {"needed": False}
        assert c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
        assert [a["note"] for a in c.get("/api/adjustments").json()] == ["old instance"]
        # restoring again is only possible for admins now
        assert c.post("/api/setup/restore", content=backup, headers=headers).status_code == 409


def test_grant_and_revoke_admin(admin):
    friend, fid = invite_friend(admin)
    assert friend.patch(f"/api/admin/users/{fid}", json={"is_admin": True}).status_code == 403
    assert admin.patch(f"/api/admin/users/{fid}", json={"is_admin": True}).json()["is_admin"] is True
    # now the first admin may leave admin rights or the instance
    assert admin.patch("/api/admin/users/1", json={"is_admin": False}).status_code == 200
    r = friend.patch(f"/api/admin/users/{fid}", json={"is_admin": False})
    assert (r.status_code, r.json()["detail"]) == (409, "last_admin")
