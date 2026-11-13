"""Tests for task domain values and validation."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from ticktask.domain.tasks import (
    TASK_DESCRIPTION_MAX_LENGTH,
    NewTask,
    Task,
    TaskPriority,
    normalize_task_description,
)


def make_task() -> Task:
    return Task(
        id=1,
        project_id=1,
        description="Write tests",
        created_date=datetime(2026, 1, 1, tzinfo=UTC),
        updated_date=datetime(2026, 1, 2, tzinfo=UTC),
        sort_order=1,
        priority=TaskPriority.MEDIUM,
        archived=False,
        completed=False,
    )


def test_task_description_max_length_constant() -> None:
    assert TASK_DESCRIPTION_MAX_LENGTH == 256


def test_task_priority_values() -> None:
    assert TaskPriority.LOW.value == "Low"
    assert TaskPriority.MEDIUM.value == "Medium"
    assert TaskPriority.HIGH.value == "High"


@pytest.mark.parametrize(
    ("completed", "archived", "expected"),
    [
        (False, False, True),
        (True, False, False),
        (False, True, False),
        (True, True, False),
    ],
)
def test_task_is_active_truth_table(
    completed: bool, archived: bool, expected: bool
) -> None:
    task = replace(make_task(), completed=completed, archived=archived)
    assert task.is_active is expected


def test_task_value_is_frozen() -> None:
    task: Any = make_task()
    with pytest.raises(AttributeError):
        task.description = "Changed"


def test_new_task_holds_persist_values() -> None:
    new_task = NewTask(
        project_id=3,
        description="New",
        sort_order=2,
        priority=TaskPriority.HIGH,
        archived=True,
        completed=False,
    )
    assert new_task.project_id == 3
    assert new_task.sort_order == 2
    assert new_task.priority is TaskPriority.HIGH
    assert new_task.archived is True
    assert new_task.completed is False


def test_normalize_task_description_strips_surrounding_whitespace() -> None:
    assert normalize_task_description("  Write tests  ") == "Write tests"


@pytest.mark.parametrize("value", [7, None, 3.5])
def test_normalize_task_description_rejects_non_string(value: object) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        normalize_task_description(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["", "   "])
def test_normalize_task_description_rejects_empty(value: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_task_description(value)


def test_normalize_task_description_accepts_max_length() -> None:
    value = "a" * TASK_DESCRIPTION_MAX_LENGTH
    assert normalize_task_description(value) == value


@pytest.mark.parametrize("length", [257, 400])
def test_normalize_task_description_rejects_over_max_length(length: int) -> None:
    with pytest.raises(ValueError, match="characters or fewer"):
        normalize_task_description("a" * length)
