"""SQLAlchemy implementation of the application transaction boundary."""

from __future__ import annotations

import sys
from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ticktask.adapters.repositories.sqlalchemy import (
    SqlAlchemyProjectRepository,
    SqlAlchemyTaskRepository,
)


class SqlAlchemyUnitOfWork:
    """Bind repositories to one SQLAlchemy session and transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory: sessionmaker[Session] = session_factory
        self._session: Session | None = None
        self.projects: SqlAlchemyProjectRepository
        self.tasks: SqlAlchemyTaskRepository

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self.projects = SqlAlchemyProjectRepository(self._session)
        self.tasks = SqlAlchemyTaskRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        self._session = None
        try:
            if exc_type is not None:
                try:
                    session.rollback()
                except SQLAlchemyError as error:
                    print(f"Transaction rollback failed: {error}", file=sys.stderr)
        finally:
            session.close()

    def commit(self) -> None:
        """Commit all changes made through the repositories."""
        session = self._session
        if session is None:
            raise RuntimeError("commit called outside of context manager")
        session.commit()


class SqlAlchemyUnitOfWorkFactory:
    """Create a fresh SQLAlchemy unit of work for each use case."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory: sessionmaker[Session] = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)


__all__: list[str] = ["SqlAlchemyUnitOfWork", "SqlAlchemyUnitOfWorkFactory"]
