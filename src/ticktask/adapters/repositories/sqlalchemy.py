"""SQLAlchemy repository adapters and ORM/domain mapping."""

from dataclasses import replace
from datetime import datetime
from typing import Any, cast

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ticktask.application.exceptions import (
    ProjectNameConflictError,
    ProjectNotFoundError,
)
from ticktask.domain.projects import Project
from ticktask.domain.tasks import NewTask, Task
from ticktask.adapters.repositories.orm import ProjectRow, TaskRow, utcnow


_ACTIVE_TASK: ColumnElement[bool] = and_(
    TaskRow.archived.is_(False), TaskRow.completed.is_(False)
)
_COMPLETED_TASK: ColumnElement[bool] = and_(
    TaskRow.archived.is_(False), TaskRow.completed.is_(True)
)
_DISPLAY_GROUP: ColumnElement[Any] = case(
    (_ACTIVE_TASK, 0),
    (_COMPLETED_TASK, 1),
    else_=2,
)


def _task_display_order() -> tuple[ColumnElement[Any], ...]:
    return (
        _DISPLAY_GROUP.asc(),
        case((_ACTIVE_TASK, TaskRow.sort_order)).asc(),
        case((_ACTIVE_TASK, TaskRow.created_date)).asc(),
        case((_ACTIVE_TASK, TaskRow.id)).asc(),
        case((_COMPLETED_TASK, TaskRow.updated_date)).desc(),
        case((_COMPLETED_TASK, TaskRow.id)).desc(),
        case((TaskRow.archived.is_(True), TaskRow.updated_date)).desc(),
        case((TaskRow.archived.is_(True), TaskRow.id)).desc(),
    )


def _is_foreign_key_error(error: IntegrityError) -> bool:
    return "FOREIGN KEY" in str(error.orig or "").upper()


class SQLAlchemyProjectRepository:
    """Persist projects using a caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session: Session = session

    def all(self) -> list[Project]:
        rows = self._session.scalars(select(ProjectRow).order_by(ProjectRow.id)).all()
        return [_project_from_row(row) for row in rows]

    def get(self, project_id: int) -> Project | None:
        row = self._session.get(ProjectRow, project_id)
        return None if row is None else _project_from_row(row)

    def get_by_name(self, name: str) -> Project | None:
        row = self._session.execute(
            select(ProjectRow).where(ProjectRow.name == name)
        ).scalar_one_or_none()
        return None if row is None else _project_from_row(row)

    def add(self, name: str) -> Project:
        row = ProjectRow(name=name)
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()
            raise ProjectNameConflictError(
                f"Project name already exists: {name}"
            ) from error
        return _project_from_row(row)


class SQLAlchemyTaskRepository:
    """Persist tasks using a caller-owned SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session: Session = session

    def list_visible_for_project(self, project_id: int) -> list[Task]:
        rows = self._session.scalars(
            select(TaskRow)
            .where(
                TaskRow.project_id == project_id,
                TaskRow.archived.is_(False),
            )
            .order_by(*_task_display_order())
        ).all()
        return [_task_from_row(row) for row in rows]

    def list_all_for_project(self, project_id: int) -> list[Task]:
        rows = self._session.scalars(
            select(TaskRow)
            .where(TaskRow.project_id == project_id)
            .order_by(*_task_display_order())
        ).all()
        return [_task_from_row(row) for row in rows]

    def get(self, project_id: int, task_id: int) -> Task | None:
        row = self._session.execute(
            select(TaskRow).where(
                TaskRow.id == task_id,
                TaskRow.project_id == project_id,
            )
        ).scalar_one_or_none()
        return None if row is None else _task_from_row(row)

    def next_active_order(self, project_id: int) -> int:
        current_max = self._session.scalar(
            select(func.max(TaskRow.sort_order)).where(
                TaskRow.project_id == project_id,
                _ACTIVE_TASK,
            )
        )
        return (current_max or 0) + 1

    def normalize_active_order(self, project_id: int) -> None:
        normalized_order = (
            func.row_number()
            .over(order_by=(TaskRow.sort_order, TaskRow.created_date, TaskRow.id))
            .label("normalized_order")
        )
        ordered_tasks = (
            select(TaskRow.id.label("task_id"), normalized_order)
            .where(TaskRow.project_id == project_id, _ACTIVE_TASK)
            .cte("ordered_tasks")
        )
        normalized_value = (
            select(ordered_tasks.c.normalized_order)
            .where(ordered_tasks.c.task_id == TaskRow.id)
            .scalar_subquery()
        )
        self._session.execute(
            update(TaskRow)
            .where(
                TaskRow.id.in_(select(ordered_tasks.c.task_id)),
                TaskRow.sort_order != normalized_value,
            )
            .values(sort_order=normalized_value, updated_date=utcnow())
            .execution_options(synchronize_session=False)
        )

    def add(self, task: NewTask) -> Task:
        row = TaskRow(
            project_id=task.project_id,
            description=task.description,
            sort_order=task.sort_order,
            priority=task.priority,
            archived=task.archived,
            completed=task.completed,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()
            if _is_foreign_key_error(error):
                raise ProjectNotFoundError(
                    f"Project not found: {task.project_id}"
                ) from error
            raise
        return _task_from_row(row)

    def save(self, task: Task) -> Task:
        saved = replace(task, updated_date=_sqlite_datetime(utcnow()))
        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(TaskRow)
                .where(TaskRow.id == task.id, TaskRow.project_id == task.project_id)
                .values(
                    description=saved.description,
                    updated_date=saved.updated_date,
                    sort_order=saved.sort_order,
                    priority=saved.priority,
                    archived=saved.archived,
                    completed=saved.completed,
                )
                .execution_options(synchronize_session=False)
            ),
        )
        if result.rowcount != 1:
            raise LookupError(f"Task row not found: {task.id}")
        return saved


def _project_from_row(row: ProjectRow) -> Project:
    return Project(id=row.id, name=row.name)


def _task_from_row(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        project_id=row.project_id,
        description=row.description,
        created_date=_sqlite_datetime(row.created_date),
        updated_date=_sqlite_datetime(row.updated_date),
        sort_order=row.sort_order,
        priority=row.priority,
        archived=row.archived,
        completed=row.completed,
    )


def _sqlite_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


__all__: list[str] = ["SQLAlchemyProjectRepository", "SQLAlchemyTaskRepository"]
