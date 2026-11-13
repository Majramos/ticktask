"""Tests for presenter and formatting helpers."""

from datetime import UTC, datetime

from ticktask.adapters.presenters import (
    ALL_TASKS_EMPTY_MESSAGE,
    DEFAULT_TIMER_TONE_COLORS,
    TIMER_LABELS,
    TIMER_TONE_COLORS,
    VISIBLE_TASKS_EMPTY_MESSAGE,
    format_seconds,
    format_task_datetime,
    format_timer_status,
    render_all_tasks,
    render_visible_tasks,
    task_status,
    timer_label,
)
from ticktask.application.timers import TimerSnapshot
from ticktask.domain.tasks import Task, TaskPriority
from ticktask.domain.timer import TimerKind, TimerSpec


def make_task(
    *,
    task_id: int = 1,
    description: str = "task",
    completed: bool = False,
    archived: bool = False,
    priority: TaskPriority = TaskPriority.MEDIUM,
    created_date: datetime | None = None,
    updated_date: datetime | None = None,
) -> Task:
    return Task(
        id=task_id,
        project_id=1,
        description=description,
        created_date=created_date or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        updated_date=updated_date or datetime(2026, 1, 2, 13, 30, tzinfo=UTC),
        sort_order=1,
        priority=priority,
        archived=archived,
        completed=completed,
    )


def make_snapshot(
    *,
    kind: TimerKind = TimerKind.FOCUS,
    remaining_seconds: int = 1500,
    running: bool = False,
    auto_start: bool = True,
) -> TimerSnapshot:
    return TimerSnapshot(
        timers=(TimerSpec(kind, remaining_seconds),),
        current_index=0,
        remaining_seconds=remaining_seconds,
        running=running,
        auto_start=auto_start,
    )


def test_format_seconds_clamps_negative_and_formats_mm_ss() -> None:
    assert format_seconds(0) == "00:00"
    assert format_seconds(59) == "00:59"
    assert format_seconds(60) == "01:00"
    assert format_seconds(125) == "02:05"
    assert format_seconds(-3) == "00:00"


def test_format_task_datetime_handles_naive_and_aware_values() -> None:
    naive = datetime(2026, 1, 1, 12, 0, tzinfo=UTC).replace(tzinfo=None)
    aware = datetime(2026, 1, 1, 13, 0, tzinfo=UTC)
    local_aware = aware

    assert format_task_datetime(naive) == "2026-01-01 12:00 UTC"
    assert format_task_datetime(aware) == "2026-01-01 13:00 UTC"
    assert format_task_datetime(local_aware) == "2026-01-01 13:00 UTC"


def test_timer_label_uses_known_labels() -> None:
    assert timer_label(TimerKind.FOCUS) == "Focus"
    assert timer_label(TimerKind.SHORT_BREAK) == "Short Break"
    assert timer_label(TimerKind.LONG_BREAK) == "Long Break"
    assert TIMER_LABELS[TimerKind.FOCUS] == "Focus"


def test_format_timer_status_without_project() -> None:
    status = format_timer_status(make_snapshot(running=False, auto_start=False))
    assert status == ("Paused | Current: Focus | Remaining: 25:00 | Auto-start: Off")


def test_format_timer_status_with_project_and_running() -> None:
    status = format_timer_status(
        make_snapshot(running=True, remaining_seconds=90, auto_start=True),
        project_name="Inbox",
    )
    assert status == (
        "Running | Project: Inbox | Current: Focus | Remaining: 01:30 | Auto-start: On"
    )


def test_task_status_reflects_flags() -> None:
    assert task_status(make_task()) == "Active"
    assert task_status(make_task(completed=True)) == "Completed"
    assert task_status(make_task(archived=True)) == "Archived"
    assert (
        task_status(make_task(completed=True, archived=True)) == "Completed, Archived"
    )


def test_render_visible_tasks_empty() -> None:
    assert render_visible_tasks([], 0) == VISIBLE_TASKS_EMPTY_MESSAGE


def test_render_visible_tasks_marks_selection_and_completed() -> None:
    output = render_visible_tasks(
        [
            make_task(task_id=1, description="first"),
            make_task(task_id=2, description="done", completed=True),
        ],
        selected_index=1,
    )

    assert "  first" in output
    assert "> done" in output
    assert "  Status: Completed" in output
    assert "Priority: Medium" in output


def test_render_all_tasks_empty_and_content() -> None:
    assert render_all_tasks([]) == ALL_TASKS_EMPTY_MESSAGE
    output = render_all_tasks(
        [
            make_task(
                description="A",
                archived=True,
                completed=False,
                priority=TaskPriority.HIGH,
            )
        ]
    )

    assert "- A" in output
    assert "Priority: High" in output
    assert "Status: Archived" in output
    assert "2026-01-01 12:00 UTC" in output


def test_timer_tone_color_maps_have_defaults() -> None:
    assert set(TIMER_TONE_COLORS) == {
        TimerKind.FOCUS,
        TimerKind.SHORT_BREAK,
        TimerKind.LONG_BREAK,
    }
    assert DEFAULT_TIMER_TONE_COLORS.background == "#1a212b"
    assert TIMER_TONE_COLORS[TimerKind.FOCUS].accent == "#38bdf8"
