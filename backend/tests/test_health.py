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


def test_backup_before_migration(tmp_path, monkeypatch):
    """An existing database that needs migrations is copied first; only the newest backups stay."""
    import sqlite3

    from alembic import command
    from alembic.config import Config

    from pendel import db
    from pendel.config import get_settings

    monkeypatch.setenv("PENDEL_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    try:
        cfg = Config()
        cfg.set_main_option("script_location", str(db.Path(db.__file__).parent / "migrations"))
        with db.migration_connection(db.get_engine()) as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "ed9001896d87")  # an older schema
        db.get_engine().dispose()
        monkeypatch.setattr(db, "BACKUPS_KEPT", 2)
        for i in range(3):
            (tmp_path / "backups").mkdir(exist_ok=True)
            (tmp_path / "backups" / f"pendel-before-0.0.{i}-old.db").write_text("x")
        db.migrate()
        backups = sorted((tmp_path / "backups").glob("*.db"))
        assert len(backups) == 2
        fresh = [b for b in backups if "-old" not in b.name]
        (copy,) = fresh
        version = sqlite3.connect(copy).execute("select version_num from alembic_version").fetchone()
        assert version == ("ed9001896d87",)
        # nothing to migrate -> no new backup
        db.migrate()
        assert len(list((tmp_path / "backups").glob("*.db"))) == 2
    finally:
        db.get_engine().dispose()
        get_settings.cache_clear()
        db.get_engine.cache_clear()
