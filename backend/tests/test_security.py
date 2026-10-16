import time

from fastapi.testclient import TestClient

from pendel import totp

from .conftest import PASSWORD

EMAIL = "admin@example.org"


def _enable_totp(admin) -> tuple[str, list[str]]:
    setup = admin.post("/api/me/totp/setup", json={"password": PASSWORD}).json()
    assert setup["uri"].startswith("otpauth://totp/Pendel:admin%40example.org?secret=")
    # a code from the previous window, so the following logins can use the current one
    code = totp.code_at(setup["secret"], time.time() - totp.PERIOD)
    r = admin.post("/api/me/totp/enable", json={"code": code})
    assert r.status_code == 200, r.text
    return setup["secret"], r.json()["codes"]


def _fresh(client) -> TestClient:
    return TestClient(client.app, headers={"X-Requested-With": "pendel"})


def test_totp_rfc6238_vector():
    # RFC 6238 test secret "12345678901234567890", T = 59 s -> 94287082 (8 digits) -> 287082
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.code_at(secret, 59) == "287082"


def test_login_with_totp_and_recovery_code(admin):
    secret, codes = _enable_totp(admin)
    assert len(codes) == 10 and admin.get("/api/me").json()["totp_enabled"]
    other = _fresh(admin)

    r = other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert (r.status_code, r.json()["detail"]) == (401, "totp_required")
    r = other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, "totp": "000000"})
    assert r.json()["detail"] == "invalid_totp"
    code = totp.code_at(secret, time.time())
    assert (
        other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, "totp": code}).status_code
        == 200
    )
    # the same code cannot be used twice
    r = other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, "totp": code})
    assert r.json()["detail"] == "invalid_totp"

    # recovery codes work once, case and dashes don't matter
    rc = codes[0].upper().replace("-", "")
    assert (
        other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, "totp": rc}).status_code
        == 200
    )
    r = other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD, "totp": rc})
    assert r.json()["detail"] == "invalid_totp"
    assert admin.get("/api/me/totp").json() == {"enabled": True, "recovery_codes_left": 9}

    # integrations (token exchange) need the code as well
    r = other.post("/api/auth/token", json={"email": EMAIL, "password": PASSWORD, "name": "HA"})
    assert r.json()["detail"] == "totp_required"
    r = other.post(
        "/api/auth/token", json={"email": EMAIL, "password": PASSWORD, "name": "HA", "totp": codes[1]}
    )
    assert r.status_code == 201


def test_disable_totp_needs_password_and_code(admin):
    secret, codes = _enable_totp(admin)
    assert admin.post("/api/me/totp/disable", json={"password": "wrong"}).status_code == 400
    r = admin.post("/api/me/totp/disable", json={"password": PASSWORD})
    assert r.json()["detail"] == "totp_required"
    assert (
        admin.post("/api/me/totp/disable", json={"password": PASSWORD, "totp": codes[0]}).status_code == 204
    )
    assert admin.get("/api/me/totp").json() == {"enabled": False, "recovery_codes_left": 0}
    other = _fresh(admin)
    assert other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


def test_enable_requires_valid_code(admin):
    assert admin.post("/api/me/totp/setup", json={"password": "wrong-password"}).status_code == 400
    secret = admin.post("/api/me/totp/setup", json={"password": PASSWORD}).json()["secret"]
    stale = totp.code_at(secret, time.time() - 10 * totp.PERIOD)
    assert admin.post("/api/me/totp/enable", json={"code": stale}).status_code == 400
    assert not admin.get("/api/me").json()["totp_enabled"]


def test_admin_can_reset_totp(admin):
    _enable_totp(admin)
    r = admin.post("/api/admin/invitations", json={"note": "x"}).json()
    friend = _fresh(admin)
    friend.post(
        f"/api/invitations/{r['token']}/accept",
        json={"email": "friend@example.org", "password": PASSWORD, "display_name": "F"},
    )
    fid = friend.get("/api/me").json()["id"]
    setup = friend.post("/api/me/totp/setup", json={"password": PASSWORD}).json()
    friend.post("/api/me/totp/enable", json={"code": totp.code_at(setup["secret"], time.time())})
    assert admin.delete(f"/api/admin/users/{fid}/totp").status_code == 204
    assert friend.get("/api/me").status_code == 401  # sessions ended
    r = friend.post("/api/auth/login", json={"email": "friend@example.org", "password": PASSWORD})
    assert r.status_code == 200 and not r.json()["totp_enabled"]


def test_sessions_list_and_logout_elsewhere(admin):
    other = _fresh(admin)
    other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    sessions = admin.get("/api/me/sessions").json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    assert admin.delete("/api/me/sessions").status_code == 204
    assert other.get("/api/me").status_code == 401
    assert admin.get("/api/me").status_code == 200
    assert len(admin.get("/api/me/sessions").json()) == 1


def test_password_change_ends_other_sessions(admin):
    other = _fresh(admin)
    other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    new = "another long password"
    r = admin.post("/api/me/password", json={"current_password": PASSWORD, "new_password": new})
    assert r.status_code == 204
    assert other.get("/api/me").status_code == 401
    assert admin.get("/api/me").status_code == 200


def test_account_limit_counts_failures_from_any_address(admin):
    from pendel.auth import account_limiter, login_limiter

    other = _fresh(admin)
    for _ in range(account_limiter.attempts):
        login_limiter._hits.clear()  # as if every guess came from another address
        assert other.post("/api/auth/login", json={"email": EMAIL, "password": "nope"}).status_code == 401
    login_limiter._hits.clear()
    r = other.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 429


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"


def test_oversized_body_rejected(admin):
    r = admin.post(
        "/api/adjustments", content=b"x" * (1024 * 1024 + 1), headers={"Content-Type": "application/json"}
    )
    assert (r.status_code, r.json()["detail"]) == (413, "request_too_large")
