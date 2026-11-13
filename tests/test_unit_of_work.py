"""Tests for the SQLAlchemy unit of work."""

from pathlib import Path

import pytest

from ticktask.adapters.repositories import (
    SqlAlchemyUnitOfWork,
    SqlAlchemyUnitOfWorkFactory,
)
from ticktask.domain.tasks import NewTask, TaskPriority
from ticktask.infrastructure import Database


def test_unit_of_work_commit_persists_changes(tmp_path: Path) -> None:
    with Database(tmp_path / "uow.db") as database:
        database.initialize()
        factory = SqlAlchemyUnitOfWorkFactory(database.session_factory)

        with factory() as uow:
            project = uow.projects.add("Inbox")
            uow.tasks.add(
                NewTask(
                    project_id=project.id,
                    description="task",
                    sort_order=1,
                    priority=TaskPriority.MEDIUM,
                    archived=False,
                    completed=False,
                )
            )
            uow.commit()

        with factory() as uow:
            assert len(uow.projects.all()) == 1
            assert len(uow.tasks.list_all_for_project(project.id)) == 1


def test_unit_of_work_rolls_back_on_exception(tmp_path: Path) -> None:
    with Database(tmp_path / "uow.db") as database:
        database.initialize()
        factory = SqlAlchemyUnitOfWorkFactory(database.session_factory)

        with pytest.raises(RuntimeError, match="boom"), factory() as uow:
            uow.projects.add("Inbox")
            raise RuntimeError("boom")

        with factory() as uow:
            assert uow.projects.all() == []


def test_commit_outside_context_raises(tmp_path: Path) -> None:
    with Database(tmp_path / "uow.db") as database:
        database.initialize()
        uow = SqlAlchemyUnitOfWork(database.session_factory)
        with pytest.raises(RuntimeError, match="outside of context manager"):
            uow.commit()


def test_exit_without_enter_is_safe(tmp_path: Path) -> None:
    with Database(tmp_path / "uow.db") as database:
        database.initialize()
        uow = SqlAlchemyUnitOfWork(database.session_factory)
        uow.__exit__(None, None, None)


def test_factory_creates_fresh_instances(tmp_path: Path) -> None:
    with Database(tmp_path / "uow.db") as database:
        database.initialize()
        factory = SqlAlchemyUnitOfWorkFactory(database.session_factory)

        first = factory()
        second = factory()

        assert first is not second


def test_rollback_failure_is_logged_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with Database(tmp_path / "uow.db") as database:
        database.initialize()

        with (
            pytest.raises(ValueError, match="user error"),
            SqlAlchemyUnitOfWork(database.session_factory) as uow,
        ):
            from sqlalchemy.exc import SQLAlchemyError

            def failing_rollback() -> None:
                raise SQLAlchemyError("rollback broken")

            uow._session.rollback = failing_rollback  # type: ignore[method-assign, union-attr]
            raise ValueError("user error")

        captured = capsys.readouterr()
        assert "Transaction rollback failed" in captured.err
