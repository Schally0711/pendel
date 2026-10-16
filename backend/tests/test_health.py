from pendel import __version__


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": __version__}


def test_spa_serving(tmp_path, monkeypatch):
    static = tmp_path / "static"
    (static / "_app").mkdir(parents=True)
    (static / "index.html").write_text("<html>app</html>")
    (static / "manifest.webmanifest").write_text("{}")
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setenv("PENDEL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PENDEL_STATIC_DIR", str(static))
    from fastapi.testclient import TestClient

    from pendel.config import get_settings
    from pendel.db import get_engine, get_sessionmaker
    from pendel.main import create_app

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/history").text == "<html>app</html>"
        assert c.get("/history").headers["cache-control"] == "no-cache"
        assert c.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
        assert c.get("/../secret.txt").text == "<html>app</html>"
        assert c.get("/api/health").json()["status"] == "ok"
