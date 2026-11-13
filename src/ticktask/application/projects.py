"""Project application service."""

from ticktask.application.ports import UnitOfWorkFactory
from ticktask.domain.projects import Project, normalize_project_name


class ProjectService:
    """Execute project use cases through an injected transaction boundary."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory: UnitOfWorkFactory = unit_of_work_factory

    def list_projects(self) -> list[Project]:
        """Return all projects sorted by identifier."""
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.projects.all()

    def get_project(self, project_id: int) -> Project | None:
        """Return a project by identifier, if present."""
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.projects.get(project_id)

    def get_project_by_name(self, name: str) -> Project | None:
        """Return a project by normalized name, if present."""
        normalized_name = normalize_project_name(name)
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.projects.get_by_name(normalized_name)

    def create_project(self, name: str) -> Project:
        """Validate and create a project."""
        normalized_name = normalize_project_name(name)
        with self._unit_of_work_factory() as unit_of_work:
            project = unit_of_work.projects.add(normalized_name)
            unit_of_work.commit()
            return project


__all__: list[str] = ["ProjectService"]
