"""Tests for database lifecycle and configuration."""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ticktask.adapters.repositories.orm import ProjectRow
from ticktask.infrastructure import Database, DatabaseError, default_database_path


def test_default_database_path_ends_with_db_name() -> None:
    path = default_database_path()
    assert path.name == "ticktask.db"
    assert path.is_absolute()


def test_database_exposes_path_and_engine(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    with Database(db_path) as database:
        assert database.path == db_path
        assert database.engine.url.database == str(db_path)


def test_exists_reports_file_presence(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    with Database(db_path) as database:
        assert database.exists() is False
        database.initialize()
        assert database.exists() is True


def test_initialize_creates_schema_and_required_indexes(tmp_path: Path) -> None:
    with Database(tmp_path / "db.sqlite") as database:
        database.initialize()
        with database.engine.connect() as connection:
            rows = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")
            ).fetchall()
        names = {row[0] for row in rows}
        assert "project" in names
        assert "task" in names
        assert "ux_project_name" in names
        assert "ix_task_active_order" in names


def test_initialize_enables_foreign_keys(tmp_path: Path) -> None:
    with Database(tmp_path / "db.sqlite") as database:
        database.initialize()
        with database.session_factory() as session:
            session.add(
                __import__(
                    "ticktask.adapters.repositories.orm", fromlist=["TaskRow"]
                ).TaskRow(
                    project_id=999,
                    description="orphan",
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()


def test_unique_project_name_index_is_enforced(tmp_path: Path) -> None:
    with Database(tmp_path / "db.sqlite") as database:
        database.initialize()
        with database.session_factory() as session:
            session.add(ProjectRow(name="Inbox"))
            session.commit()
        with database.session_factory() as session:
            session.add(ProjectRow(name="Inbox"))
            with pytest.raises(IntegrityError):
                session.commit()


def test_reset_deletes_database_file(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    with Database(db_path) as database:
        database.initialize()
        assert db_path.exists() is True
        assert database.reset() is True
        assert db_path.exists() is False
        assert database.reset() is False


def test_initialize_raises_database_error_on_unwritable_parent(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocker")
    with (
        Database(blocker / "db.sqlite") as database,
        pytest.raises(DatabaseError, match="Cannot create database"),
    ):
        database.initialize()


def test_reset_raises_database_error_on_unlink_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "db.sqlite"
    with Database(db_path) as database:
        database.initialize()

        def broken_unlink(self: Path) -> None:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "unlink", broken_unlink)
        with pytest.raises(DatabaseError, match="Cannot delete database"):
            database.reset()


def test_context_manager_disposes_on_exception(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    with pytest.raises(RuntimeError, match="boom"), Database(db_path) as database:
        database.initialize()
        raise RuntimeError("boom")
    # Engine is disposed (idempotent) — no assertions beyond no deadlock.
    assert database.path == db_path
