"""Task input adapter for user-interface actions."""

from ticktask.application.tasks import TaskService
from ticktask.domain.tasks import Task, TaskPriority


class TaskController:
    """Expose task workflows and route create-versus-update submissions."""

    def __init__(self, service: TaskService) -> None:
        self._service: TaskService = service

    def list_visible_tasks(self, project_id: int) -> list[Task]:
        """Return tasks shown on the primary task screen."""
        return self._service.list_visible_tasks(project_id)

    def list_all_tasks(self, project_id: int) -> list[Task]:
        """Return active, completed, and archived tasks."""
        return self._service.list_all_tasks(project_id)

    def save_task(
        self,
        project_id: int,
        task_id: int | None,
        *,
        description: str,
        priority: TaskPriority,
        completed: bool,
        archived: bool,
    ) -> Task:
        """Create a new task or update the identified task."""
        if task_id is None:
            return self._service.create_task(
                project_id,
                description,
                priority=priority,
                completed=completed,
                archived=archived,
            )
        return self._service.update_task(
            project_id,
            task_id,
            description=description,
            priority=priority,
            completed=completed,
            archived=archived,
        )


__all__ = ["TaskController"]
