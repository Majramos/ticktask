"""Tests for controller input adapters."""

from tests.fakes import create_services
from ticktask.adapters.controllers.projects import ProjectController
from ticktask.adapters.controllers.tasks import TaskController
from ticktask.domain.tasks import TaskPriority


def test_project_controller_delegates_to_service() -> None:
    project_service, _, _ = create_services()
    controller = ProjectController(project_service)

    created = controller.create_project("Inbox")

    assert controller.get_project(created.id) == created
    assert controller.list_projects() == [created]


def test_project_controller_returns_none_for_missing_project() -> None:
    project_service, _, _ = create_services()
    controller = ProjectController(project_service)
    assert controller.get_project(404) is None


def test_task_controller_delegates_list_operations() -> None:
    project_service, task_service, _ = create_services()
    project = project_service.create_project("Inbox")
    controller = TaskController(task_service)

    controller.save_task(
        project.id,
        None,
        description="visible",
        priority=TaskPriority.MEDIUM,
        completed=False,
        archived=False,
    )
    completed = controller.save_task(
        project.id,
        None,
        description="done",
        priority=TaskPriority.HIGH,
        completed=True,
        archived=False,
    )
    archived = controller.save_task(
        project.id,
        None,
        description="archived",
        priority=TaskPriority.LOW,
        completed=False,
        archived=True,
    )

    visible = controller.list_visible_tasks(project.id)
    all_tasks = controller.list_all_tasks(project.id)

    assert [task.description for task in visible] == ["visible", "done"]
    assert [task.description for task in all_tasks] == ["visible", "done", "archived"]
    assert completed.priority is TaskPriority.HIGH
    assert archived.archived is True


def test_task_controller_save_task_updates_existing_task() -> None:
    project_service, task_service, _ = create_services()
    project = project_service.create_project("Inbox")
    controller = TaskController(task_service)
    created = controller.save_task(
        project.id,
        None,
        description="before",
        priority=TaskPriority.MEDIUM,
        completed=False,
        archived=False,
    )

    updated = controller.save_task(
        project.id,
        created.id,
        description="after",
        priority=TaskPriority.LOW,
        completed=True,
        archived=False,
    )

    assert updated.id == created.id
    assert updated.description == "after"
    assert updated.priority is TaskPriority.LOW
    assert updated.completed is True
