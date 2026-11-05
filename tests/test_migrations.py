from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from app.core.config import get_settings


def test_migrations_upgrade_downgrade_and_metadata(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/migration-test.db"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "head")
        engine = create_engine(url)
        assert {
            "users",
            "sessions",
            "clients",
            "leads",
            "campaigns",
            "content",
            "reports",
            "approval_actions",
        } <= set(inspect(engine).get_table_names())
        engine.dispose()
        command.check(config)
        command.downgrade(config, "base")
        engine = create_engine(url)
        assert inspect(engine).get_table_names() == ["alembic_version"]
        engine.dispose()
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()


def test_readiness_distinguishes_unmigrated_database(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core.config import Settings

    with TestClient(
        create_app(
            Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/empty.db")
        )
    ) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/ready").status_code == 503


def test_consistent_private_backup(tmp_path, monkeypatch):
    import sqlite3
    import stat
    from app.utils.backup import backup

    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE data (value TEXT)")
        connection.execute("INSERT INTO data VALUES ('preserved')")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{source}")
    get_settings.cache_clear()
    try:
        destination = backup(tmp_path / "copy.sqlite3")
        with sqlite3.connect(destination) as copy:
            assert copy.execute("SELECT value FROM data").fetchone()[0] == "preserved"
        assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    finally:
        get_settings.cache_clear()
