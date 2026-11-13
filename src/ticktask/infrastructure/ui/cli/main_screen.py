"""Main task screen and timer-only screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ticktask.adapters.controllers import TaskController
from ticktask.adapters.presenters import (
    VISIBLE_TASKS_EMPTY_MESSAGE,
    format_timer_status,
    render_visible_tasks,
)
from ticktask.application.timers import TimerSnapshot
from ticktask.domain.tasks import Task
from ticktask.infrastructure.ui.cli.timer_widgets import TimerCard, TimerCarousel

if TYPE_CHECKING:
    from ticktask.infrastructure.ui.cli.entry import TickTask

__all__: list[str] = ["MainScreen", "PomodoroScreen", "TimerCard", "TimerCarousel"]

_COMMON_TIMER_BINDINGS: list[Binding] = [
    Binding("space", "toggle_run", "Start/Pause"),
    Binding("right", "next_timer", "Next"),
    Binding("r", "restart_timer", "Restart"),
]


class _TimerScreen(Screen[None]):
    """Shared presentation behavior for timer screens."""

    STOPPED_BACKGROUND: ClassVar[str] = "#0f1115"
    RUNNING_BACKGROUND: ClassVar[str] = "#002b36"

    def __init__(self, snapshot: TimerSnapshot) -> None:
        super().__init__()
        self.timer_snapshot: TimerSnapshot = snapshot
        self.status_text: str = ""
        self.background_color: str = self.STOPPED_BACKGROUND
        self._rendered_snapshot: TimerSnapshot | None = None
        self._rendered_status_text: str | None = None
        self._status_key: tuple[bool, int, int, bool, str | None] | None = None
        self._carousel: TimerCarousel | None = None
        self._status_widget: Static | None = None

    def _refresh_timer_view(self) -> None:
        self._apply_status()
        self.set_timer_snapshot(self.timer_snapshot)

    def get_carousel(self) -> TimerCarousel:
        """Return the mounted timer carousel."""
        if self._carousel is None:
            self._carousel = self.query_one(TimerCarousel)
        return self._carousel

    def set_timer_snapshot(self, snapshot: TimerSnapshot) -> None:
        """Render a timer snapshot and its running background."""
        self.timer_snapshot = snapshot
        if not self._has_dom():
            return
        previous = self._rendered_snapshot
        if previous is None or previous.running != snapshot.running:
            self.apply_run_state_background(snapshot.running)
        self.get_carousel().render_snapshot(snapshot)
        self._rendered_snapshot = snapshot

    def set_status_text(self, status_text: str) -> None:
        """Update the status line."""
        self.status_text = status_text
        self._apply_status()

    def update_timer_display(
        self, snapshot: TimerSnapshot, project_name: str | None
    ) -> None:
        """Render the timer snapshot and formatted status line."""
        self.set_timer_snapshot(snapshot)
        status_key = (
            snapshot.running,
            snapshot.current_index,
            snapshot.remaining_seconds,
            snapshot.auto_start,
            project_name,
        )
        if self._status_key != status_key:
            self.set_status_text(format_timer_status(snapshot, project_name))
            self._status_key = status_key

    def apply_run_state_background(self, running: bool) -> str:
        """Apply and return the current screen background color."""
        self.background_color = (
            self.RUNNING_BACKGROUND if running else self.STOPPED_BACKGROUND
        )
        if self.is_mounted:
            self.styles.background = self.background_color
        return self.background_color

    def action_toggle_run(self) -> None:
        self._app().toggle_run()

    def action_toggle_auto_start(self) -> None:
        self._app().toggle_auto_start()

    def action_next_timer(self) -> None:
        self._app().advance_timer()

    def action_restart_timer(self) -> None:
        self._app().restart_timer()

    def _apply_status(self) -> None:
        if not self._has_dom() or self._rendered_status_text == self.status_text:
            return
        if self._status_widget is None:
            self._status_widget = self.query_one("#status", Static)
        self._status_widget.update(Text(self.status_text))
        self._rendered_status_text = self.status_text

    def _app(self) -> TickTask:
        return cast("TickTask", self.app)

    def _has_dom(self) -> bool:
        return self.is_mounted


class PomodoroScreen(_TimerScreen):
    """Timer-only Pomodoro screen."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        *_COMMON_TIMER_BINDINGS,
        Binding("a", "toggle_auto_start", "Auto"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TimerCarousel(self.timer_snapshot)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_timer_view()

    def on_show(self) -> None:
        self._refresh_timer_view()


class MainScreen(_TimerScreen):
    """Primary timer and task management screen."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        *_COMMON_TIMER_BINDINGS,
        Binding("a", "toggle_auto_start", "Auto/Archive"),
        Binding("v", "view_all_tasks", "All Tasks"),
        Binding("p", "change_project", "Change Project"),
        Binding("t", "create_task", "New Task"),
        Binding("up", "select_task_up", "Task Up"),
        Binding("down", "select_task_down", "Task Down"),
        Binding("enter", "task_enter", "Edit"),
    ]

    def __init__(
        self, snapshot: TimerSnapshot, task_controller: TaskController
    ) -> None:
        super().__init__(snapshot)
        self._task_controller: TaskController = task_controller
        self.current_project_id: int | None = None
        self.current_project_name: str | None = None
        self.visible_tasks: list[Task] = []
        self.selected_task_index: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="project-background-name")
        yield Static(id="current-project")
        yield TimerCarousel(self.timer_snapshot)
        yield Static(id="status")
        yield Container(
            Container(
                Static("Tasks", id="tasks-title"),
                Static(VISIBLE_TASKS_EMPTY_MESSAGE, id="tasks-list"),
                id="tasks-card",
            ),
            id="tasks-panel",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_view()

    def on_show(self) -> None:
        self._refresh_view()

    def set_project(self, project_id: int | None, project_name: str | None) -> None:
        """Update the active project rendered by the screen."""
        self.current_project_id = project_id
        self.current_project_name = project_name
        self._apply_project_banner()

    def clear_state(self) -> None:
        """Clear project, task, status, and selection state."""
        self.current_project_name = None
        self.current_project_id = None
        self.visible_tasks = []
        self.selected_task_index = 0
        self.status_text = ""
        self.background_color = self.STOPPED_BACKGROUND
        self._refresh_view()

    def refresh_tasks(self, *, selected_task_id: int | None = None) -> None:
        """Load and render tasks for the active project."""
        if self.current_project_id is None:
            self.visible_tasks = []
            self.selected_task_index = 0
            self._render_tasks()
            return

        self.visible_tasks = self._task_controller.list_visible_tasks(
            self.current_project_id
        )
        if selected_task_id is not None:
            self._select_task(selected_task_id)
        self._clamp_selected_task_index()
        self._render_tasks()

    def action_create_task(self) -> None:
        if self.current_project_id is not None:
            self._app().open_task_form()

    def action_view_all_tasks(self) -> None:
        if self.current_project_id is not None:
            self._app().show_all_tasks_screen()

    def action_select_task_up(self) -> None:
        if self.visible_tasks:
            self.selected_task_index = max(0, self.selected_task_index - 1)
            self._render_tasks()

    def action_select_task_down(self) -> None:
        if self.visible_tasks:
            self.selected_task_index = min(
                len(self.visible_tasks) - 1,
                self.selected_task_index + 1,
            )
            self._render_tasks()

    def action_task_enter(self) -> None:
        if self.visible_tasks:
            self._app().open_task_form(self.visible_tasks[self.selected_task_index])

    def action_change_project(self) -> None:
        self._app().change_project()

    def _refresh_view(self) -> None:
        self._apply_project_banner()
        self._render_tasks()
        self._refresh_timer_view()

    def _select_task(self, task_id: int) -> None:
        self.selected_task_index = next(
            (
                index
                for index, task in enumerate(self.visible_tasks)
                if task.id == task_id
            ),
            self.selected_task_index,
        )

    def _clamp_selected_task_index(self) -> None:
        if not self.visible_tasks:
            self.selected_task_index = 0
            return
        last_task_index = len(self.visible_tasks) - 1
        self.selected_task_index = min(
            max(self.selected_task_index, 0), last_task_index
        )

    def _apply_project_banner(self) -> None:
        if not self._has_dom():
            return
        project_name = self.current_project_name
        self.query_one("#project-background-name", Static).update(
            Text("" if project_name is None else project_name.upper())
        )
        self.query_one("#current-project", Static).update(
            Text("" if project_name is None else f"Project: {project_name}")
        )

    def _render_tasks(self) -> None:
        if self._has_dom():
            rendered_tasks = render_visible_tasks(
                self.visible_tasks, self.selected_task_index
            )
            self.query_one("#tasks-list", Static).update(Text(rendered_tasks))
