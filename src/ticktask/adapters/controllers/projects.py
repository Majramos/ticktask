"""Project input adapter for user interface actions."""

from ticktask.application.projects import ProjectService
from ticktask.domain.projects import Project


class ProjectController:
    """Expose project use cases without coupling a UI to application services."""

    def _init_(self, service: ProjectService) -> None:
        self._service: ProjectService = service

    def list_projects(self) -> list[Project]:
        """Return all available projects."""
        return self._service.list_projects()

    def get_project(self, project_id: int) -> Project | None:
        """Return a project by identifier, if present."""
        return self._service.get_project(project_id)

    def create_project(self, name: str) -> Project:
        """Create a project from UI input."""
        return self._service.create_project(name)


_all_: list[str] = ["ProjectController"]
