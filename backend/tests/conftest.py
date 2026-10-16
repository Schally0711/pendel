import pytest
from fastapi.testclient import TestClient

from pendel.setup import setup_code

PASSWORD = "correct horse battery"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENDEL_SECURE_COOKIES", "false")
    from pendel.auth import account_limiter, login_limiter
    from pendel.config import get_settings
    from pendel.db import get_engine, get_sessionmaker

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    from pendel import setup

    setup.reset()
    login_limiter._hits.clear()
    account_limiter._hits.clear()
    from pendel.main import create_app

    with TestClient(create_app(), headers={"X-Requested-With": "pendel"}) as c:
        yield c


@pytest.fixture
def admin(client):
    """Client logged in as the first (admin) user."""
    r = client.post(
        "/api/setup",
        json={
            "email": "Admin@Example.org",
            "password": PASSWORD,
            "display_name": "Admin",
            "setup_code": setup_code(),
        },
    )
    assert r.status_code == 201, r.text
    return client
