"""Task creation and editing screen."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Protocol, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Checkbox, Footer, Header, Select, Static, TextArea
from textual.widgets.text_area import EditResult, Location

from ticktask.adapters.controllers import TaskController
from ticktask.domain.tasks import (
    TASK_DESCRIPTION_MAX_LENGTH,
    Task,
    TaskPriority,
    normalize_task_description,
)

_PRIORITY_BY_NAME: dict[str, TaskPriority] = {
    "low": TaskPriority.LOW,
    "medium": TaskPriority.MEDIUM,
    "high": TaskPriority.HIGH,
}


def _coerce_priority(value: object) -> TaskPriority:
    if isinstance(value, TaskPriority):
        return value
    if isinstance(value, str):
        return _PRIORITY_BY_NAME.get(value.strip().lower(), TaskPriority.MEDIUM)
    return TaskPriority.MEDIUM


@dataclass(frozen=True, slots=True)
class _TaskFormValues:
    description: str
    priority: TaskPriority
    completed: bool
    archived: bool


@dataclass(frozen=True, slots=True)
class _TaskFormWidgets:
    description: TextArea
    priority: Select[object]
    completed: Checkbox
    archived: Checkbox


class _TaskSubmitScreen(Protocol):
    def action_task_submit(self) -> None: ...


class TaskDescriptionTextArea(TextArea):
    """TextArea constrained to the task description domain limit."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("enter", "submit_task", "Save", show=False, priority=True),
        Binding("shift+enter", "insert_newline", "Newline", show=False, priority=True),
    ]

    def replace(
        self,
        insert: str,
        start: Location,
        end: Location,
        *,
        maintain_selection_offset: bool = True,
    ) -> EditResult:
        selected_text = self.get_text_range(start, end)
        available_capacity = TASK_DESCRIPTION_MAX_LENGTH - (
            len(self.text) - len(selected_text)
        )
        return super().replace(
            insert[: max(0, available_capacity)],
            start,
            end,
            maintain_selection_offset=maintain_selection_offset,
        )

    def load_text(self, text: str) -> None:
        super().load_text(text[:TASK_DESCRIPTION_MAX_LENGTH])

    def action_submit_task(self) -> None:
        cast(_TaskSubmitScreen, self.screen).action_task_submit()

    def action_insert_newline(self) -> None:
        start, end = self.selection
        self.replace("\n", start, end, maintain_selection_offset=False)


class TaskFormScreen(Screen[int | None]):
    """Full-screen task creation and editing flow."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("enter", "task_submit", "Save"),
        Binding("escape", "task_cancel", "Cancel"),
        Binding("l", "task_priority_low", "Low", show=False),
        Binding("m", "task_priority_medium", "Medium", show=False),
        Binding("h", "task_priority_high", "High", show=False),
        Binding("c", "task_toggle_completed", "Completed", show=False),
        Binding("a", "task_toggle_archived", "Archived", show=False),
    ]

    def __init__(
        self,
        *,
        task_controller: TaskController,
        current_project_id: int,
        current_project_name: str,
        task: Task | None = None,
    ) -> None:
        super().__init__()
        self._task_controller = task_controller
        self._current_project_id = current_project_id
        self._current_project_name = current_project_name
        self._task_view: Task | None = task

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Container(
                Static("Create Task", id="task-form-title"),
                TaskDescriptionTextArea(
                    text="",
                    placeholder=(
                        f"Task description (max {TASK_DESCRIPTION_MAX_LENGTH} chars)"
                    ),
                    soft_wrap=True,
                    id="task-description",
                ),
                id="task-description-input",
            ),
            Container(
                Select(
                    [
                        ("Low", TaskPriority.LOW),
                        ("Medium", TaskPriority.MEDIUM),
                        ("High", TaskPriority.HIGH),
                    ],
                    prompt="Priority",
                    allow_blank=False,
                    value=TaskPriority.MEDIUM,
                    id="task-priority-select",
                ),
                Checkbox("Completed", id="task-completed-checkbox"),
                Checkbox("Archived", id="task-archived-checkbox"),
                id="task-form-meta-row",
            ),
            Static("", id="task-form-error"),
            Static(
                "Shortcuts: l/m/h priority, c completed, a archived, •"
                "Enter save, Shift+Enter newline, Esc cancel",
                id="task-form-help",
            ),
            id="task-form",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._populate_form()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "task-description":
            self._resize_task_description(event.text_area)

    def action_task_submit(self) -> None:
        self._submit_task_form()

    def action_task_cancel(self) -> None:
        self.dismiss(None)

    def action_task_priority_low(self) -> None:
        self._set_priority(TaskPriority.LOW)

    def action_task_priority_medium(self) -> None:
        self._set_priority(TaskPriority.MEDIUM)

    def action_task_priority_high(self) -> None:
        self._set_priority(TaskPriority.HIGH)

    def action_task_toggle_completed(self) -> None:
        self._toggle_checkbox("#task-completed-checkbox")

    def action_task_toggle_archived(self) -> None:
        self._toggle_checkbox("#task-archived-checkbox")

    def _populate_form(self) -> None:
        title = "Edit Task" if self._task_view is not None else "Create Task"
        self.query_one("#task-form-title", Static).update(title)
        widgets = self._form_widgets()
        values = self._initial_values()
        widgets.description.load_text(values.description)
        widgets.priority.value = values.priority
        widgets.completed.value = values.completed
        widgets.archived.value = values.archived
        self.query_one("#task-form-error", Static).update("")
        self._resize_task_description(widgets.description)
        widgets.description.focus()

    def _submit_task_form(self) -> None:
        error_widget = self.query_one("#task-form-error", Static)
        values = self._read_form_values(error_widget)
        if values is None:
            return

        try:
            saved_task = self._save_task(values)
        except ValueError as error:
            error_widget.update(str(error))
            return
        self.dismiss(saved_task.id)

    def _read_form_values(self, error_widget: Static) -> _TaskFormValues | None:
        widgets = self._form_widgets()
        try:
            description = normalize_task_description(widgets.description.text)
        except ValueError as error:
            error_widget.update(str(error))
            return None
        return _TaskFormValues(
            description=description,
            priority=_coerce_priority(widgets.priority.value),
            completed=widgets.completed.value,
            archived=widgets.archived.value,
        )

    def _initial_values(self) -> _TaskFormValues:
        if self._task_view is None:
            return _TaskFormValues("", TaskPriority.MEDIUM, False, False)
        return _TaskFormValues(
            self._task_view.description,
            self._task_view.priority,
            self._task_view.completed,
            self._task_view.archived,
        )

    def _form_widgets(self) -> _TaskFormWidgets:
        return _TaskFormWidgets(
            description=self.query_one("#task-description", TextArea),
            priority=self.query_one("#task-priority-select", Select),
            completed=self.query_one("#task-completed-checkbox", Checkbox),
            archived=self.query_one("#task-archived-checkbox", Checkbox),
        )

    def _set_priority(self, priority: TaskPriority) -> None:
        self.query_one("#task-priority-select", Select).value = priority

    def _toggle_checkbox(self, selector: str) -> None:
        checkbox = self.query_one(selector, Checkbox)
        checkbox.value = not checkbox.value

    def _save_task(self, values: _TaskFormValues) -> Task:
        return self._task_controller.save_task(
            self._current_project_id,
            None if self._task_view is None else self._task_view.id,
            description=values.description,
            priority=values.priority,
            completed=values.completed,
            archived=values.archived,
        )

    def _resize_task_description(
        self, description_widget: TextArea | None = None
    ) -> None:
        if description_widget is None:
            description_widget = self.query_one("#task-description", TextArea)
        wrap_width = self._task_description_wrap_width(description_widget)
        text_lines = description_widget.text.splitlines() or [""]
        wrapped_lines = sum(
            max(1, math.ceil(max(1, len(line)) / wrap_width)) for line in text_lines
        )
        description_widget.styles.height = min(12, max(3, wrapped_lines + 2))

    @staticmethod
    def _task_description_wrap_width(description_widget: TextArea) -> int:
        for attr_name in ("content_size", "size"):
            size = getattr(description_widget, attr_name, None)
            width = getattr(size, "width", 0) if size is not None else 0
            if isinstance(width, (int, float)) and width > 0:
                return max(1, int(width) - 2)
        return 40


__all__: list[str] = ["TaskDescriptionTextArea", "TaskFormScreen"]
