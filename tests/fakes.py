"""Typed in-memory adapters used by domain and application tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType

from ticktask.application.exceptions import ProjectNameConflictError
from ticktask.application.projects import ProjectService
from ticktask.application.tasks import TaskService, sort_tasks_for_display
from ticktask.application.timers import TimerSnapshot
from ticktask.domain.projects import Project
from ticktask.domain.tasks import NewTask, Task


class InMemoryStore:
    """Shared state behind lightweight repository instances."""

    def __init__(self) -> None:
        self.projects: dict[int, Project] = {}
        self.tasks: dict[int, Task] = {}
        self.next_project_id = 1
        self.next_task_id = 1
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def timestamp(self) -> datetime:
        """Return a deterministic, increasing timestamp."""
        self.now += timedelta(seconds=1)
        return self.now

    def clone(self) -> InMemoryStore:
        """Return a shallow copy of this store for transaction isolation."""
        snapshot = InMemoryStore()
        snapshot.projects = dict(self.projects)
        snapshot.tasks = dict(self.tasks)
        snapshot.next_project_id = self.next_project_id
        snapshot.next_task_id = self.next_task_id
        snapshot.now = self.now
        return snapshot


class InMemoryProjectRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def all(self) -> list[Project]:
        return sorted(self._store.projects.values(), key=lambda project: project.id)

    def get(self, project_id: int) -> Project | None:
        return self._store.projects.get(project_id)

    def get_by_name(self, name: str) -> Project | None:
        return next(
            (
                project
                for project in self._store.projects.values()
                if project.name == name
            ),
            None,
        )

    def add(self, name: str) -> Project:
        if self.get_by_name(name) is not None:
            raise ProjectNameConflictError(f"Project name already exists: {name}")
        project = Project(id=self._store.next_project_id, name=name)
        self._store.next_project_id += 1
        self._store.projects[project.id] = project
        return project


class InMemoryTaskRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def list_visible_for_project(self, project_id: int) -> list[Task]:
        tasks = [
            task
            for task in self._store.tasks.values()
            if task.project_id == project_id and not task.archived
        ]
        return sort_tasks_for_display(tasks)

    def list_all_for_project(self, project_id: int) -> list[Task]:
        tasks = [
            task for task in self._store.tasks.values() if task.project_id == project_id
        ]
        return sort_tasks_for_display(tasks)

    def get(self, project_id: int, task_id: int) -> Task | None:
        task = self._store.tasks.get(task_id)
        if task is None or task.project_id != project_id:
            return None
        return task

    def next_active_order(self, project_id: int) -> int:
        return (
            max(
                (
                    task.sort_order
                    for task in self._store.tasks.values()
                    if task.project_id == project_id and task.is_active
                ),
                default=0,
            )
            + 1
        )

    def normalize_active_order(self, project_id: int) -> None:
        project_tasks = [
            task for task in self._store.tasks.values() if task.project_id == project_id
        ]
        active = sorted(
            (task for task in project_tasks if task.is_active),
            key=lambda task: (task.sort_order, task.created_date, task.id),
        )
        for index, task in enumerate(active, 1):
            if task.sort_order != index:
                self._store.tasks[task.id] = replace(
                    task,
                    sort_order=index,
                    updated_date=self._store.timestamp(),
                )

    def add(self, task: NewTask) -> Task:
        timestamp = self._store.timestamp()
        saved = Task(
            id=self._store.next_task_id,
            project_id=task.project_id,
            description=task.description,
            created_date=timestamp,
            updated_date=timestamp,
            sort_order=task.sort_order,
            priority=task.priority,
            archived=task.archived,
            completed=task.completed,
        )
        self._store.next_task_id += 1
        self._store.tasks[saved.id] = saved
        return saved

    def save(self, task: Task) -> Task:
        saved = replace(task, updated_date=self._store.timestamp())
        self._store.tasks[saved.id] = saved
        return saved


class InMemoryUnitOfWork:
    def __init__(self, store: InMemoryStore) -> None:
        self._shared_store: InMemoryStore = store
        self._local_store: InMemoryStore | None = None
        self.projects: InMemoryProjectRepository
        self.tasks: InMemoryTaskRepository
        self.committed = False

    def __enter__(self) -> InMemoryUnitOfWork:
        self._local_store = self._shared_store.clone()
        self.projects = InMemoryProjectRepository(self._local_store)
        self.tasks = InMemoryTaskRepository(self._local_store)
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._local_store = None
        return None

    def commit(self) -> None:
        local_store = self._local_store
        if local_store is None:
            raise RuntimeError("commit called outside of context manager")
        self._shared_store.projects = dict(local_store.projects)
        self._shared_store.tasks = dict(local_store.tasks)
        self._shared_store.next_project_id = local_store.next_project_id
        self._shared_store.next_task_id = local_store.next_task_id
        self._shared_store.now = local_store.now
        self.committed = True


class InMemoryUnitOfWorkFactory:
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store or InMemoryStore()
        self.created: list[InMemoryUnitOfWork] = []

    def __call__(self) -> InMemoryUnitOfWork:
        unit_of_work = InMemoryUnitOfWork(self.store)
        self.created.append(unit_of_work)
        return unit_of_work


class RecordingPublisher:
    def __init__(self) -> None:
        self.snapshots: list[TimerSnapshot] = []

    def start(self) -> None:
        """Provide the same lifecycle surface as the real publisher."""

    def publish(self, snapshot: TimerSnapshot) -> None:
        self.snapshots.append(snapshot)

    def close(self) -> None:
        """Provide the same lifecycle surface as the real publisher."""


def create_services() -> tuple[ProjectService, TaskService, InMemoryUnitOfWorkFactory]:
    """Return application services backed by one in-memory store."""
    factory = InMemoryUnitOfWorkFactory()
    return ProjectService(factory), TaskService(factory), factory


__all__ = [
    "InMemoryStore",
    "InMemoryUnitOfWorkFactory",
    "RecordingPublisher",
    "create_services",
]
