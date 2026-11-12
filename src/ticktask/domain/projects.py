"""Project domain values and validation."""

from dataclasses import dataclass

PROJECT_NAME_MAX_LENGTH: int = 30


@dataclass(frozen=True, slots=True)
class Project:
    """A detached project entity."""

    id: int
    name: str


def normalize_project_name(name: str) -> str:
    """Return a validated, canonical project name."""
    if not isinstance(name, str):
        raise TypeError("Project name must be a string.")
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Project name cannot be empty.")
    if len(normalized_name) > PROJECT_NAME_MAX_LENGTH:
        raise ValueError(
            f"Project name must be {PROJECT_NAME_MAX_LENGTH} characters or fewer."
        )
    return normalized_name


__all__: list[str] = [
    "PROJECT_NAME_MAX_LENGTH",
    "Project",
    "normalize_project_name",
]
