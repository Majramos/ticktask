from dataclasses import dataclass

from ticktask.adapters.controllers.projects import ProjectController
from ticktask.adapters.controllers.tasks import TaskController


@dataclass(frozen=True, slots=True)
class TaskManagementControllers:
    projects: ProjectController
    tasks: TaskController


__all__: list[str] = [
    "ProjectController",
    "TaskController",
    "TaskManagementControllers",
]
