"""Task application service and ordering policy."""

from collections.abc import Sequence
from dataclasses import replace

from ticktask.application.exceptions import ProjectNotFoundError, TaskNotFoundError
from ticktask.application.ports import UnitOfWork, UnitOfWorkFactory
from ticktask.domain.tasks import (
    NewTask,
    Task,
    TaskPriority,
    normalize_task_description,
)


def sort_tasks_for_display(tasks: Sequence[Task]) -> list[Task]:
    """Return tasks in display order: active, completed, then archived."""
    active = sorted(
        (task for task in tasks if task.is_active),
        key=lambda task: (task.sort_order, task.created_date, task.id),
    )
    completed = sorted(
        (task for task in tasks if task.completed and not task.archived),
        key=lambda task: (task.updated_date, task.id),
        reverse=True,
    )
    archived = sorted(
        (task for task in tasks if task.archived),
        key=lambda task: (task.updated_date, task.id),
        reverse=True,
    )
    return active + completed + archived


class TaskService:
    """Execute task use cases independently from the persistence framework."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def create_task(
        self,
        project_id: int,
        description: str,
        *,
        priority: TaskPriority = TaskPriority.MEDIUM,
        completed: bool = False,
        archived: bool = False,
    ) -> Task:
        """Create a task and assign its active ordering position."""
        normalized_description = normalize_task_description(description)
        with self._unit_of_work_factory() as unit_of_work:
            self._require_project(unit_of_work.projects.get(project_id), project_id)
            sort_order = (
                unit_of_work.tasks.next_active_order(project_id)
                if self._is_active_flags(completed=completed, archived=archived)
                else 0
            )
            task = unit_of_work.tasks.add(
                NewTask(
                    project_id=project_id,
                    description=normalized_description,
                    sort_order=sort_order,
                    priority=priority,
                    completed=completed,
                    archived=archived,
                )
            )
            unit_of_work.commit()
        return task

    def update_task(
        self,
        project_id: int,
        task_id: int,
        *,
        description: str | None = None,
        priority: TaskPriority | None = None,
        completed: bool | None = None,
        archived: bool | None = None,
    ) -> Task:
        """Update a task and maintain active ordering in one transaction."""
        with self._unit_of_work_factory() as unit_of_work:
            self._require_project(unit_of_work.projects.get(project_id), project_id)
            current = unit_of_work.tasks.get(project_id, task_id)
            if current is None:
                raise TaskNotFoundError(f"Task not found: {task_id}")

            updated = self._apply_changes(
                current,
                description=description,
                priority=priority,
                completed=completed,
                archived=archived,
            )
            updated = self._synchronize_active_order(
                unit_of_work,
                current=current,
                updated=updated,
            )
            try:
                saved = unit_of_work.tasks.save(updated)
            except LookupError as error:
                raise TaskNotFoundError(f"Task not found: {task_id}") from error
            if current.is_active and not updated.is_active:
                unit_of_work.tasks.normalize_active_order(project_id)
            unit_of_work.commit()
            return saved

    def list_visible_tasks(self, project_id: int) -> list[Task]:
        """Return active tasks followed by recent completed tasks."""
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.tasks.list_visible_for_project(project_id)

    def list_all_tasks(self, project_id: int) -> list[Task]:
        """Return active, completed, and archived tasks in display order."""
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.tasks.list_all_for_project(project_id)

    @staticmethod
    def _require_project(project: object | None, project_id: int) -> None:
        if project is None:
            raise ProjectNotFoundError(f"Project not found: {project_id}")

    @staticmethod
    def _apply_changes(
        task: Task,
        *,
        description: str | None,
        priority: TaskPriority | None,
        completed: bool | None,
        archived: bool | None,
    ) -> Task:
        return replace(
            task,
            description=(
                normalize_task_description(description)
                if description is not None
                else task.description
            ),
            priority=priority if priority is not None else task.priority,
            completed=completed if completed is not None else task.completed,
            archived=archived if archived is not None else task.archived,
        )

    @staticmethod
    def _synchronize_active_order(
        unit_of_work: UnitOfWork,
        *,
        current: Task,
        updated: Task,
    ) -> Task:
        was_active = current.is_active
        is_active = updated.is_active

        if was_active and not is_active:
            return replace(updated, sort_order=0)
        if not was_active and is_active:
            return replace(
                updated,
                sort_order=unit_of_work.tasks.next_active_order(current.project_id),
            )
        if is_active and updated.sort_order < 1:
            return replace(
                updated,
                sort_order=unit_of_work.tasks.next_active_order(current.project_id),
            )
        return updated

    @staticmethod
    def _is_active_flags(*, completed: bool, archived: bool) -> bool:
        return not (completed or archived)


__all__: list[str] = ["TaskService", "sort_tasks_for_display"]
