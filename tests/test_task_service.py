"""Tests for the task application service and ordering policy."""

import pytest

from tests.fakes import InMemoryUnitOfWorkFactory, create_services
from ticktask.application.exceptions import ProjectNotFoundError, TaskNotFoundError
from ticktask.application.projects import ProjectService
from ticktask.application.tasks import TaskService, sort_tasks_for_display
from ticktask.domain.tasks import TaskPriority


@pytest.fixture
def factory() -> InMemoryUnitOfWorkFactory:
    _, _, created_factory = create_services()
    return created_factory


@pytest.fixture
def task_service(factory: InMemoryUnitOfWorkFactory) -> TaskService:
    return TaskService(factory)


@pytest.fixture
def project_id(factory: InMemoryUnitOfWorkFactory) -> int:
    return int(ProjectService(factory).create_project("Inbox").id)


def test_sort_tasks_for_display_orders_groups(
    task_service: TaskService, project_id: int
) -> None:
    active = task_service.create_task(project_id, "active")
    completed_draft = task_service.create_task(project_id, "done")
    archived_draft = task_service.create_task(project_id, "old")
    task_service.update_task(project_id, completed_draft.id, completed=True)
    task_service.update_task(project_id, archived_draft.id, archived=True)
    all_tasks = task_service.list_all_tasks(project_id)
    completed = all_tasks[1]
    archived_task = all_tasks[2]
    another_active = task_service.create_task(project_id, "second active")

    ordered = task_service.list_visible_tasks(project_id)
    all_tasks = task_service.list_all_tasks(project_id)

    assert [task.id for task in ordered] == [
        active.id,
        another_active.id,
        completed.id,
    ]
    assert [task.id for task in all_tasks] == [
        active.id,
        another_active.id,
        completed.id,
        archived_task.id,
    ]
    assert sort_tasks_for_display([]) == []
    assert active.sort_order == 1
    assert completed.sort_order == 0
    assert archived_task.sort_order == 0
    assert another_active.sort_order == 2


def test_create_task_assigns_next_active_order(
    task_service: TaskService, project_id: int
) -> None:
    first = task_service.create_task(project_id, "first")
    second = task_service.create_task(project_id, "second")

    assert first.sort_order == 1
    assert second.sort_order == 2


def test_create_task_marks_completed_and_archived_with_zero_order(
    task_service: TaskService, project_id: int
) -> None:
    completed = task_service.create_task(project_id, "done", completed=True)
    archived = task_service.create_task(project_id, "old", archived=True)

    assert completed.sort_order == 0
    assert archived.sort_order == 0


def test_create_task_supports_priority(
    task_service: TaskService, project_id: int
) -> None:
    task = task_service.create_task(project_id, "urgent", priority=TaskPriority.HIGH)
    assert task.priority is TaskPriority.HIGH


@pytest.mark.parametrize("description", ["", "   "])
def test_create_task_rejects_blank_description(
    task_service: TaskService, project_id: int, description: str
) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        task_service.create_task(project_id, description)


def test_create_task_requires_existing_project(task_service: TaskService) -> None:
    with pytest.raises(ProjectNotFoundError, match="Project not found: 404"):
        task_service.create_task(404, "lost")


def test_list_visible_tasks_hides_archived(
    task_service: TaskService, project_id: int
) -> None:
    kept = task_service.create_task(project_id, "kept")
    hidden = task_service.create_task(project_id, "hidden")
    task_service.update_task(project_id, hidden.id, archived=True)

    visible = task_service.list_visible_tasks(project_id)

    assert [task.id for task in visible] == [kept.id]


def test_list_visible_tasks_empty_project(
    task_service: TaskService, project_id: int
) -> None:
    assert task_service.list_visible_tasks(project_id) == []


def test_update_task_changes_description_and_priority(
    task_service: TaskService, project_id: int
) -> None:
    task = task_service.create_task(project_id, "before")

    updated = task_service.update_task(
        project_id, task.id, description="after", priority=TaskPriority.LOW
    )

    assert updated.description == "after"
    assert updated.priority is TaskPriority.LOW
    assert updated.sort_order == task.sort_order


def test_update_task_completing_zeroes_sort_order_and_normalizes(
    task_service: TaskService, project_id: int
) -> None:
    task_service.create_task(project_id, "first")
    second = task_service.create_task(project_id, "second")
    task_service.create_task(project_id, "third")

    task_service.update_task(project_id, second.id, completed=True)

    visible = task_service.list_visible_tasks(project_id)
    assert [task.description for task in visible] == ["first", "third", "second"]
    all_tasks = task_service.list_all_tasks(project_id)
    assert visible[2].sort_order == 0
    assert visible[2].completed is True
    assert all_tasks[0].sort_order == 1
    assert all_tasks[1].sort_order == 2


def test_update_task_reactivating_assigns_next_order(
    task_service: TaskService, project_id: int
) -> None:
    completed = task_service.create_task(project_id, "done", completed=True)
    active = task_service.create_task(project_id, "active")

    task_service.update_task(project_id, completed.id, completed=False)

    all_tasks = task_service.list_all_tasks(project_id)
    by_id = {task.id: task for task in all_tasks}
    assert by_id[completed.id].sort_order == active.sort_order + 1
    assert by_id[completed.id].sort_order == 2


def test_update_task_active_with_low_order_gains_order(
    task_service: TaskService, project_id: int
) -> None:
    task = task_service.create_task(project_id, "task")
    task_service.update_task(project_id, task.id, completed=True)
    reactivated = task_service.update_task(project_id, task.id, completed=False)
    assert reactivated.sort_order == 1


def test_update_task_missing_project_raises(
    task_service: TaskService,
) -> None:
    with pytest.raises(ProjectNotFoundError):
        task_service.update_task(505, 1, description="x")


def test_update_task_missing_task_raises(
    task_service: TaskService, project_id: int
) -> None:
    with pytest.raises(TaskNotFoundError, match="Task not found: 999"):
        task_service.update_task(project_id, 999, description="x")


def test_update_same_state_keeps_active_sort_order(
    task_service: TaskService, project_id: int
) -> None:
    task = task_service.create_task(project_id, "task")

    updated = task_service.update_task(project_id, task.id, archived=False)

    assert updated.sort_order == 1


def test_create_task_committed_before_task_service_returns(
    task_service: TaskService, project_id: int, factory: InMemoryUnitOfWorkFactory
) -> None:
    created = task_service.create_task(project_id, "task")
    fetched = TaskService(factory).list_visible_tasks(project_id)
    assert [task.id for task in fetched] == [created.id]
