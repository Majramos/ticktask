"""Task domain values and validation."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

TASK_DESCRIPTION_MAX_LENGTH: int = 256


class TaskPriority(StrEnum):
    """Supported task priority levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass(frozen=True, slots=True)
class Task:
    """A detached task entity.

    `created_date` and `updated_date` are naive datetimes that
    represent UTC instants. Callers that need timezone-aware values
    must attach UTC before use.
    """

    id: int
    project_id: int
    description: str
    created_date: datetime
    updated_date: datetime
    sort_order: int
    priority: TaskPriority
    archived: bool
    completed: bool

    @property
    def is_active(self) -> bool:
        """Return whether the task belongs to the active ordering group."""
        return not (self.completed or self.archived)


@dataclass(frozen=True, slots=True)
class NewTask:
    """Validated values required to persist a new task."""

    project_id: int
    description: str
    sort_order: int
    priority: TaskPriority
    archived: bool
    completed: bool


def normalize_task_description(description: str) -> str:
    """Return a validated task description without surrounding whitespace."""
    if not isinstance(description, str):
        raise TypeError("Task description must be a string.")
    normalized_description = description.strip()
    if not normalized_description:
        raise ValueError("Task description cannot be empty.")
    if len(normalized_description) > TASK_DESCRIPTION_MAX_LENGTH:
        raise ValueError(
            "Task description must be "
            f"{TASK_DESCRIPTION_MAX_LENGTH} characters or fewer."
        )
    return normalized_description


__all__: list[str] = [
    "TASK_DESCRIPTION_MAX_LENGTH",
    "NewTask",
    "Task",
    "TaskPriority",
    "normalize_task_description",
]
