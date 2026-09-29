"""SQLAlchemy mappings kept outside the domain and application layers."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ticktask.domain.projects import PROJECT_NAME_MAX_LENGTH
from ticktask.domain.tasks import TASK_DESCRIPTION_MAX_LENGTH, TaskPriority

PROJECT_NAME_INDEX: Index = Index("ux_project_name", "name", unique=True)
TASK_ACTIVE_ORDER_INDEX: Index = Index(
    "ix_task_active_order",
    "project_id",
    "archived",
    "completed",
    "sort_order",
    "created_date",
    "id",
)
REQUIRED_INDEXES: tuple[Index, ...] = (PROJECT_NAME_INDEX, TASK_ACTIVE_ORDER_INDEX)


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted records."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all TickTask ORM mappings."""


class ProjectRow(Base):
    """Persistence representation of a project."""

    __tablename__ = "project"
    __table_args__ = (PROJECT_NAME_INDEX,)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(PROJECT_NAME_MAX_LENGTH), nullable=False)
    tasks: Mapped[list["TaskRow"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )


class TaskRow(Base):
    """Persistence representation of a task."""

    __tablename__ = "task"
    __table_args__ = (TASK_ACTIVE_ORDER_INDEX,)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    description: Mapped[str] = mapped_column(
        String(TASK_DESCRIPTION_MAX_LENGTH), nullable=False
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            values_callable=lambda enum_type: [member.value for member in enum_type],
            native_enum=False,
            validate_strings=True,
            name="task_priority",
        ),
        default=TaskPriority.MEDIUM,
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    project: Mapped[ProjectRow] = relationship(back_populates="tasks", lazy="raise")


__all__: list[str] = [
    "Base",
    "ProjectRow",
    "REQUIRED_INDEXES",
    "TaskRow",
    "utcnow",
]
