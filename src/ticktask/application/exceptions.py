"""Application errors exposed to outer adapters."""


class ProjectNameConflictError(ValueError):
    """Raised when a normalized project name already exists."""


class ProjectNotFoundError(ValueError):
    """Raised when a requested project does not exist."""


class TaskNotFoundError(ValueError):
    """Raised when a requested task does not exist in the project."""


__all__: list[str] = [
    "ProjectNameConflictError",
    "ProjectNotFoundError",
    "TaskNotFoundError",
]
