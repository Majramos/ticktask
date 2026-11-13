"""SQLite engine lifecycle and local database path management."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Self

from platformdirs import PlatformDirs
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ticktask.adapters.repositories.orm import REQUIRED_INDEXES, Base

_APP_NAME: str = "ticktask"
_DB_FILENAME: str = "ticktask.db"


class DatabaseError(Exception):
    """Raised when a database lifecycle operation fails."""


def default_database_path() -> Path:
    """Return the platform-specific path for the TickTask SQLite database."""
    directories = PlatformDirs(appname=_APP_NAME, appauthor=False)
    return directories.user_data_path / _DB_FILENAME


def _configure_sqlite_pragmas(
    dbapi_connection: Any,
    _connection_record: Any,
) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


class Database:
    """Own the SQLAlchemy engine, sessions, schema initialization, and reset."""

    def __init__(self, path: Path | None = None) -> None:
        self._path: Path = path if path is not None else default_database_path()
        engine_url = URL.create("sqlite+pysqlite", database=str(self._path))
        self._engine: Engine = create_engine(
            engine_url,
            echo=False,
            hide_parameters=True,
        )
        event.listen(self._engine, "connect", _configure_sqlite_pragmas)
        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine, expire_on_commit=False
        )

    @property
    def path(self) -> Path:
        """Return the configured database file path."""
        return self._path

    @property
    def engine(self) -> Engine:
        """Return the SQLAlchemy engine."""
        return self._engine

    def initialize(self) -> None:
        """Create missing schema objects without altering existing data."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            Base.metadata.create_all(self._engine)
            self._ensure_indexes()
        except OSError as error:
            raise DatabaseError(
                f"Cannot create database at {self._path}: {error}"
            ) from error
        except SQLAlchemyError as error:
            raise DatabaseError(
                f"Cannot initialize database schema at {self._path}: {error}"
            ) from error

    def exists(self) -> bool:
        """Return whether the configured SQLite file exists."""
        return self._path.is_file()

    def reset(self) -> bool:
        """Dispose connections and delete the configured database file."""
        self._engine.dispose()
        if self._path.exists():
            try:
                self._path.unlink()
            except OSError as error:
                raise DatabaseError(
                    f"Cannot delete database at {self._path}: {error}"
                ) from error
            return True
        return False

    def dispose(self) -> None:
        """Close pooled database connections."""
        self._engine.dispose()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.dispose()

    def _ensure_indexes(self) -> None:
        with self._engine.begin() as connection:
            for index in REQUIRED_INDEXES:
                index.create(connection, checkfirst=True)


__all__: list[str] = ["Database", "DatabaseError", "default_database_path"]
