"""Tests for project domain values and validation."""

import pytest

from ticktask.domain.projects import (
    PROJECT_NAME_MAX_LENGTH,
    Project,
    normalize_project_name,
)


def test_project_max_length_constant() -> None:
    assert PROJECT_NAME_MAX_LENGTH == 30


def test_project_value_is_frozen() -> None:
    project = Project(id=1, name="Inbox")
    with pytest.raises(AttributeError):
        project.name = "Changed"  # type: ignore[misc]


def test_normalize_project_name_strips_surrounding_whitespace() -> None:
    assert normalize_project_name("  Inbox  ") == "Inbox"


@pytest.mark.parametrize("value", [1, None, ["Inbox"]])
def test_normalize_project_name_rejects_non_string(value: object) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        normalize_project_name(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_project_name_rejects_empty(value: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_project_name(value)


@pytest.mark.parametrize(
    "length", [PROJECT_NAME_MAX_LENGTH - 1, PROJECT_NAME_MAX_LENGTH]
)
def test_normalize_project_name_accepts_up_to_max_length(length: int) -> None:
    assert normalize_project_name("a" * length) == "a" * length


@pytest.mark.parametrize("length", [PROJECT_NAME_MAX_LENGTH + 1, 100])
def test_normalize_project_name_rejects_over_max_length(length: int) -> None:
    with pytest.raises(ValueError, match="characters or fewer"):
        normalize_project_name("a" * length)
