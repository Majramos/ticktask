"""Read-only screen for viewing every task, including archived ones."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ticktask.adapters.controllers import TaskController
from ticktask.adapters.presenters import ALL_TASKS_EMPTY_MESSAGE, render_all_tasks
from ticktask.domain.tasks import Task

if TYPE_CHECKING:
    from ticktask.infrastructure.ui.cli.entry import TickTask


class AllTasksScreen(Screen[None]):
    """Read-only task overview that includes archived items."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "back_to_main", "Back"),
        Binding("b", "back_to_main", "Back", show=False),
    ]

    def __init__(self, task_controller: TaskController) -> None:
        super().__init__()
        self._task_controller: TaskController = task_controller
        self.current_project_id: int | None = None
        self.current_project_name: str | None = None
        self.tasks: list[Task] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="all-tasks-current-project")
        yield Container(
            Container(
                Static("All Tasks", id="all-tasks-title"),
                Static(
                    "Includes active, completed, and archived tasks. Read-only view.",
                    id="all-tasks-help",
                ),
                VerticalScroll(
                    Static(ALL_TASKS_EMPTY_MESSAGE, id="all-tasks-list"),
                    id="all-tasks-scroll",
                ),
                id="all-tasks-card",
            ),
            id="all-tasks-screen",
        )
        yield Footer()

    def on_show(self) -> None:
        self._apply_project_label()
        self._render_tasks()

    def set_project(self, project_id: int | None, project_name: str | None) -> None:
        """Update the project rendered by the overview."""
        self.current_project_id = project_id
        self.current_project_name = project_name
        self._apply_project_label()

    def clear_state(self) -> None:
        """Clear project and task state."""
        self.current_project_name = None
        self.current_project_id = None
        self.tasks = []
        self._apply_project_label()
        self._render_tasks()

    def refresh_tasks(self) -> None:
        """Load and render all tasks for the active project."""
        self.tasks = (
            []
            if self.current_project_id is None
            else self._task_controller.list_all_tasks(self.current_project_id)
        )
        self._render_tasks()

    def action_back_to_main(self) -> None:
        self._app().show_main_screen()

    def _apply_project_label(self) -> None:
        if self._has_dom():
            self.query_one("#all-tasks-current-project", Static).update(
                Text(
                    ""
                    if self.current_project_name is None
                    else f"Project: {self.current_project_name}"
                )
            )

    def _render_tasks(self) -> None:
        if self._has_dom():
            self.query_one("#all-tasks-list", Static).update(
                Text(render_all_tasks(self.tasks))
            )

    def _has_dom(self) -> bool:
        return self.is_mounted

    def _app(self) -> TickTask:
        return cast("TickTask", self.app)


__all__: list[str] = ["AllTasksScreen"]
