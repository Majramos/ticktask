"""Framework-free view formatting shared by TickTask user interfaces."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from ticktask.application.timers import TimerSnapshot
from ticktask.domain.tasks import Task
from ticktask.domain.timer import TimerKind


SECONDS_PER_MINUTE: Final[int] = 60
TASK_DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M UTC"
VISIBLE_TASKS_EMPTY_MESSAGE: Final[str] = "No tasks yet. Press 't' to create one."
ALL_TASKS_EMPTY_MESSAGE: Final[str] = "No tasks found."


@dataclass(frozen=True, slots=True)
class TimerToneColors:
    """Colors shared by Textual timer cards and the tray icon."""

    background: str
    accent: str


DEFAULT_TIMER_TONE_COLORS: Final[TimerToneColors] = TimerToneColors(
    background="#1a212b",
    accent="#cbd5e1",
)

TIMER_TONE_COLORS: Final[dict[TimerKind, TimerToneColors]] = {
    TimerKind.FOCUS: TimerToneColors(background="#0f2a43", accent="#38bdf8"),
    TimerKind.SHORT_BREAK: TimerToneColors(background="#1c2b1a", accent="#86efac"),
    TimerKind.LONG_BREAK: TimerToneColors(background="#3b2100", accent="#fb923c"),
}

TIMER_LABELS: Final[dict[TimerKind, str]] = {
    TimerKind.FOCUS: "Focus",
    TimerKind.SHORT_BREAK: "Short Break",
    TimerKind.LONG_BREAK: "Long Break",
}


def format_seconds(seconds: int) -> str:
    """Return a MM:SS representation for a number of seconds."""
    minutes, remaining_seconds = divmod(max(0, seconds), SECONDS_PER_MINUTE)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def format_task_datetime(value: datetime) -> str:
    """Return UTC datetime text for task metadata."""
    return _as_utc(value).strftime(TASK_DATETIME_FORMAT)


def timer_label(kind: TimerKind) -> str:
    """Return the user-facing label for a timer kind."""
    return TIMER_LABELS[kind]


def format_timer_status(
    snapshot: TimerSnapshot,
    project_name: str | None = None,
) -> str:
    """Return the status line for the current timer snapshot."""
    status_parts = ["Running" if snapshot.running else "Paused"]
    if project_name is not None:
        status_parts.append(f"Project: {project_name}")
    status_parts.extend(
        [
            f"Current: {timer_label(snapshot.current_spec.kind)}",
            f"Remaining: {format_seconds(snapshot.remaining_seconds)}",
            f"Auto-start: {'On' if snapshot.auto_start else 'Off'}",
        ]
    )
    return " | ".join(status_parts)


def task_status(task: Task) -> str:
    """Return a concise label for a task's current state."""
    statuses = [
        label
        for enabled, label in (
            (task.completed, "Completed"),
            (task.archived, "Archived"),
        )
        if enabled
    ]
    return ", ".join(statuses) or "Active"


def render_visible_tasks(tasks: Sequence[Task], selected_index: int) -> str:
    """Render the selectable task summary shown on the main screen."""
    groups = [
        _visible_task_lines(task, selected=index == selected_index)
        for index, task in enumerate(tasks)
    ]
    return _join_groups(groups) if groups else VISIBLE_TASKS_EMPTY_MESSAGE


def render_all_tasks(tasks: Sequence[Task]) -> str:
    """Render the read-only summary that includes archived tasks."""
    groups = [_all_task_lines(task) for task in tasks]
    return _join_groups(groups) if groups else ALL_TASKS_EMPTY_MESSAGE


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _visible_task_lines(task: Task, *, selected: bool) -> list[str]:
    lines = [
        f"{'>' if selected else ' '} {task.description}",
        f"  {_task_metadata(task)}",
    ]
    if task.completed:
        lines.append("  Status: Completed")
    return lines


def _all_task_lines(task: Task) -> list[str]:
    return [
        f"- {task.description}",
        f"  Priority: {task.priority.value} | Status: {task_status(task)} | ",
        f"  Created: {format_task_datetime(task.created_date)} | ",
        f"  Updated: {format_task_datetime(task.updated_date)}",
    ]


def _task_metadata(task: Task) -> str:
    return (
        f"Priority: {task.priority.value} | "
        f"Created: {format_task_datetime(task.created_date)} | "
        f"Updated: {format_task_datetime(task.updated_date)}"
    )


def _join_groups(groups: Sequence[Sequence[str]]) -> str:
    return "\n\n".join("\n".join(group) for group in groups)


__all__: list[str] = [
    "ALL_TASKS_EMPTY_MESSAGE",
    "DEFAULT_TIMER_TONE_COLORS",
    "TIMER_LABELS",
    "TIMER_TONE_COLORS",
    "TimerToneColors",
    "VISIBLE_TASKS_EMPTY_MESSAGE",
    "format_seconds",
    "format_task_datetime",
    "format_timer_status",
    "render_all_tasks",
    "render_visible_tasks",
    "task_status",
    "timer_label",
]
