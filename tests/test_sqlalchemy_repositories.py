"""Tests for SQLAlchemy repository adapters."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest

from ticktask.adapters.repositories import (
    SqlAlchemyProjectRepository,
    SqlAlchemyTaskRepository,
)
from ticktask.adapters.repositories.unit_of_work import SqlAlchemyUnitOfWork
from ticktask.application.exceptions import (
    ProjectNameConflictError,
    ProjectNotFoundError,
)
from ticktask.application.projects import ProjectService
from ticktask.application.tasks import TaskService
from ticktask.domain.tasks import NewTask, TaskPriority
from ticktask.infrastructure import Database


@pytest.fixture
def database(tmp_path: Path) -> Generator[Database]:
    with Database(tmp_path / "repos.db") as db:
        db.initialize()
        yield db


@pytest.fixture
def project_service(database: Database) -> ProjectService:
    from ticktask.adapters.repositories import SqlAlchemyUnitOfWorkFactory

    return ProjectService(SqlAlchemyUnitOfWorkFactory(database.session_factory))


@pytest.fixture
def task_service(database: Database) -> TaskService:
    from ticktask.adapters.repositories import SqlAlchemyUnitOfWorkFactory

    return TaskService(SqlAlchemyUnitOfWorkFactory(database.session_factory))


@pytest.fixture
def project_id(project_service: ProjectService) -> int:
    return project_service.create_project("Inbox").id


def test_project_repository_crud(database: Database) -> None:
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        first = uow.projects.add("Alpha")
        second = uow.projects.add("Beta")
        uow.commit()

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        assert [project.name for project in uow.projects.all()] == ["Alpha", "Beta"]
        assert uow.projects.get(first.id) == first
        assert uow.projects.get(999) is None
        assert uow.projects.get_by_name("Beta") == second
        assert uow.projects.get_by_name("Missing") is None


def test_project_repository_duplicate_name_raises_conflict(
    database: Database,
) -> None:
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        uow.projects.add("Inbox")
        uow.commit()

    with (
        SqlAlchemyUnitOfWork(database.session_factory) as uow,
        pytest.raises(ProjectNameConflictError, match="already exists"),
    ):
        uow.projects.add("Inbox")


def test_task_repository_add_and_read_roundtrip(
    task_service: TaskService, project_id: int
) -> None:
    created = task_service.create_task(project_id, "task", priority=TaskPriority.HIGH)

    visible = task_service.list_visible_tasks(project_id)
    all_tasks = task_service.list_all_tasks(project_id)

    assert len(visible) == 1
    assert visible[0].id == created.id
    assert visible[0].priority is TaskPriority.HIGH
    assert visible[0].created_date == datetime.replace(
        visible[0].created_date, tzinfo=None
    )
    assert all_tasks == visible


def test_task_repository_get_respects_project_scope(
    task_service: TaskService, project_service: ProjectService, project_id: int
) -> None:
    other_project = project_service.create_project("Other").id
    task = task_service.create_task(project_id, "task")
    other = task_service.create_task(other_project, "other")

    with SqlAlchemyUnitOfWork(
        project_service._unit_of_work_factory._session_factory  # type: ignore[attr-defined]
    ) as uow:
        assert uow.tasks.get(project_id, task.id) is not None
        assert uow.tasks.get(project_id, other.id) is None
        assert uow.tasks.get(other_project, other.id) is not None
        assert uow.tasks.get(project_id, 404) is None


def test_task_repository_visible_and_all_ordering(
    task_service: TaskService, project_id: int
) -> None:
    first = task_service.create_task(project_id, "first")
    second = task_service.create_task(project_id, "second")
    completed = task_service.create_task(project_id, "done")
    archived = task_service.create_task(project_id, "old")
    task_service.update_task(project_id, completed.id, completed=True)
    task_service.update_task(project_id, archived.id, archived=True)

    visible = task_service.list_visible_tasks(project_id)
    all_tasks = task_service.list_all_tasks(project_id)

    assert [task.id for task in visible] == [first.id, second.id, completed.id]
    assert [task.id for task in all_tasks] == [
        first.id,
        second.id,
        completed.id,
        archived.id,
    ]


def test_task_repository_next_active_order(database: Database, project_id: int) -> None:
    # This project_id is from project_service fixture — but with its own UoW factory.
    # Insert directly into the same database session_factory.
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        uow.projects.add("Local Inbox")  # project 1
        project = uow.projects.all()[0]
        task_repo = uow.tasks
        assert task_repo.next_active_order(project.id) == 1
        task_repo.add(
            NewTask(
                project_id=project.id,
                description="a",
                sort_order=3,
                priority=TaskPriority.MEDIUM,
                archived=False,
                completed=False,
            )
        )
        uow.commit()

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        project = uow.projects.all()[0]
        assert uow.tasks.next_active_order(project.id) == 4


def test_task_repository_normalize_active_order(
    database: Database,
) -> None:
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        project = uow.projects.add("Inbox")
        for order in (5, 2, 9):
            uow.tasks.add(
                NewTask(
                    project_id=project.id,
                    description=f"task-{order}",
                    sort_order=order,
                    priority=TaskPriority.MEDIUM,
                    archived=False,
                    completed=False,
                )
            )
        uow.commit()

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        project = uow.projects.all()[0]
        uow.tasks.normalize_active_order(project.id)
        uow.commit()

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        project = uow.projects.all()[0]
        tasks = uow.tasks.list_visible_for_project(project.id)
        assert [(task.description, task.sort_order) for task in tasks] == [
            ("task-2", 1),
            ("task-5", 2),
            ("task-9", 3),
        ]


def test_task_repository_add_foreign_key_error_raises_project_not_found(
    database: Database,
) -> None:
    with (
        SqlAlchemyUnitOfWork(database.session_factory) as uow,
        pytest.raises(ProjectNotFoundError, match="Project not found: 404"),
    ):
        uow.tasks.add(
            NewTask(
                project_id=404,
                description="orphan",
                sort_order=1,
                priority=TaskPriority.MEDIUM,
                archived=False,
                completed=False,
            )
        )


def test_task_repository_save_updates_and_errors_on_missing(
    database: Database,
) -> None:
    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        project = uow.projects.add("Inbox")
        task = uow.tasks.add(
            NewTask(
                project_id=project.id,
                description="before",
                sort_order=1,
                priority=TaskPriority.MEDIUM,
                archived=False,
                completed=False,
            )
        )
        uow.commit()

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        project = uow.projects.all()[0]
        task = uow.tasks.list_all_for_project(project.id)[0]
        from dataclasses import replace

        saved = uow.tasks.save(
            replace(
                task,
                description="after",
                priority=TaskPriority.HIGH,
                completed=True,
                sort_order=0,
            )
        )
        uow.commit()

    assert saved.description == "after"
    assert saved.priority is TaskPriority.HIGH
    assert saved.completed is True
    assert saved.sort_order == 0
    assert saved.updated_date.tzinfo is None

    with SqlAlchemyUnitOfWork(database.session_factory) as uow:
        from dataclasses import replace

        with pytest.raises(LookupError, match="Task row not found"):
            uow.tasks.save(replace(task, id=999))


def test_project_repository_instance(database: Database) -> None:
    with database.session_factory() as session:
        repo = SqlAlchemyProjectRepository(session)
        repo.add("Inbox")
        session.commit()

    with database.session_factory() as session:
        repo = SqlAlchemyProjectRepository(session)
        assert len(repo.all()) == 1


def test_task_repository_instance_list_all(database: Database) -> None:
    with database.session_factory() as session:
        project_repo = SqlAlchemyProjectRepository(session)
        project = project_repo.add("Inbox")
        task_repo = SqlAlchemyTaskRepository(session)
        task_repo.add(
            NewTask(
                project_id=project.id,
                description="task",
                sort_order=1,
                priority=TaskPriority.MEDIUM,
                archived=False,
                completed=False,
            )
        )
        session.commit()

    with database.session_factory() as session:
        task_repo = SqlAlchemyTaskRepository(session)
        all_tasks = task_repo.list_all_for_project(1)
        assert len(all_tasks) == 1
