import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDEL_DATA_DIR", str(tmp_path))
    from pendel.config import get_settings

    get_settings.cache_clear()
    from pendel.main import create_app

    with TestClient(create_app()) as c:
        yield c
