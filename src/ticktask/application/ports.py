"""Interfaces owned by the application layer."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, Self

from ticktask.domain.projects import Project
from ticktask.domain.tasks import NewTask, Task

if TYPE_CHECKING:
    from ticktask.application.timers import TimerSnapshot


class ProjectRepository(Protocol):
    """Persistence operations required by project use cases."""

    def all(self) -> list[Project]: ...

    def get(self, project_id: int) -> Project | None: ...

    def get_by_name(self, name: str) -> Project | None: ...

    def add(self, name: str) -> Project: ...


class TaskRepository(Protocol):
    """Persistence operations required by task use cases."""

    def list_visible_for_project(self, project_id: int) -> list[Task]: ...

    def list_all_for_project(self, project_id: int) -> list[Task]: ...

    def get(self, project_id: int, task_id: int) -> Task | None: ...

    def next_active_order(self, project_id: int) -> int: ...

    def normalize_active_order(self, project_id: int) -> None: ...

    def add(self, task: NewTask) -> Task: ...

    def save(self, task: Task) -> Task: ...


class UnitOfWork(Protocol):
    """Transaction boundary for project and task repositories."""

    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def tasks(self) -> TaskRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type UnitOfWorkFactory = Callable[[], UnitOfWork]


class TimerStatePublisher(Protocol):
    """Output port for live timer state updates."""

    def start(self) -> None: ...

    def publish(self, snapshot: TimerSnapshot) -> None: ...

    def close(self) -> None: ...


__all__ = [
    "ProjectRepository",
    "TaskRepository",
    "TimerStatePublisher",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
