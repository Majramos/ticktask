"""Textual application host and screen navigation."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding
from textual.timer import Timer

from ticktask.adapters.controllers import TaskManagementControllers
from ticktask.application.timers import PomodoroController
from ticktask.domain.projects import Project
from ticktask.domain.tasks import Task
from ticktask.infrastructure.ui.cli.all_tasks_screen import AllTasksScreen
from ticktask.infrastructure.ui.cli.main_screen import MainScreen, PomodoroScreen
from ticktask.infrastructure.ui.cli.project_form_screen import ProjectFormScreen
from ticktask.infrastructure.ui.cli.task_form_screen import TaskFormScreen


class TickTask(App[None]):
    """TickTask Textual host and presentation coordinator."""

    CSS_PATH = Path(__file__).resolve().parent / "style.tcss"
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("q", "quit", "Quit", show=True, priority=True)
    ]
    STOPPED_BACKGROUND: ClassVar[str] = MainScreen.STOPPED_BACKGROUND
    RUNNING_BACKGROUND: ClassVar[str] = MainScreen.RUNNING_BACKGROUND

    def __init__(
        self,
        timer_controller: PomodoroController,
        task_management: TaskManagementControllers | None = None,
    ) -> None:
        super().__init__()
        self._timer_controller: PomodoroController = timer_controller
        self._task_management: TaskManagementControllers | None = task_management
        self.current_project: Project | None = None
        self._tick_timer: Timer | None = None

    @property
    def pomodoro_only(self) -> bool:
        """Return whether task management is disabled."""
        return self._task_management is None

    def on_mount(self) -> None:
        if self.pomodoro_only:
            self._mount_pomodoro_screen()
            self._timer_controller.publish_current()
        else:
            self._mount_project_screens()

    def on_tick(self) -> None:
        if not self._timer_controls_enabled():
            return
        completed = self._timer_controller.tick()
        if completed:
            self.bell()
        if completed or self._timer_controller.running:
            self.update_status()
        self._sync_tick_timer()

    def update_status(self) -> None:
        """Render the current timer snapshot and status line."""
        if not self._timer_controls_enabled():
            return
        snapshot = self._timer_controller.snapshot
        project = self.current_project
        project_name = project.name if project is not None else None
        self._get_timer_screen().update_timer_display(snapshot, project_name)

    def activate_project(self, project: Project) -> None:
        """Activate a project and show its main task screen."""
        self.current_project = project
        self._show_installed_screen("main")
        self.call_after_refresh(self._refresh_main_screen_for_active_project)

    def toggle_run(self) -> None:
        """Start or pause the current timer."""
        if self._timer_controls_enabled():
            self._timer_controller.toggle_run()
            self.update_status()
            self._sync_tick_timer()

    def toggle_auto_start(self) -> None:
        """Toggle automatic startup of the next timer."""
        if self._timer_controls_enabled():
            self._timer_controller.toggle_auto_start()
            self.update_status()

    def advance_timer(self) -> None:
        """Advance to the next timer."""
        if self._timer_controls_enabled():
            self._timer_controller.advance()
            self.update_status()

    def restart_timer(self) -> None:
        """Restart the current timer."""
        if self._timer_controls_enabled():
            self._timer_controller.restart()
            self.update_status()

    def open_task_form(self, task: Task | None = None) -> None:
        """Open the create or edit task form for the active project."""
        active_project = self.current_project
        services = self._task_management
        if active_project is None or services is None:
            return
        self.push_screen(
            TaskFormScreen(
                task_controller=services.tasks,
                current_project_id=active_project.id,
                current_project_name=active_project.name,
                task=task,
            ),
            callback=self._handle_task_form_result,
        )

    def show_all_tasks_screen(self) -> None:
        """Refresh and show the read-only all-tasks screen."""
        active_project = self.current_project
        if active_project is None:
            return
        all_tasks_screen = self.get_screen("all_tasks", AllTasksScreen)
        all_tasks_screen.set_project(active_project.id, active_project.name)
        all_tasks_screen.refresh_tasks()
        self._show_installed_screen("all_tasks")

    def show_main_screen(self) -> None:
        """Return to the main task screen when a project is active."""
        if not self.pomodoro_only and self.current_project is not None:
            self._show_installed_screen("main")

    def change_project(self) -> None:
        """Pause timer activity, clear task state, and show project selection."""
        if self.pomodoro_only:
            return
        if self.current_project is not None:
            self._timer_controller.pause_and_restart()
            self.update_status()
            self._sync_tick_timer()

        self.current_project = None
        self.get_screen("main", MainScreen).clear_state()
        self.get_screen("all_tasks", AllTasksScreen).clear_state()
        self.show_project_screen()

    def show_project_screen(self) -> None:
        """Refresh and show project selection."""
        if self.pomodoro_only:
            return
        project_screen = self.get_screen("project", ProjectFormScreen)
        project_screen.refresh_projects()
        self._show_installed_screen("project")

    def _mount_pomodoro_screen(self) -> None:
        self.install_screen(
            PomodoroScreen(self._timer_controller.snapshot), name="pomodoro"
        )
        self._tick_timer = self.set_interval(1, self.on_tick)
        self._show_installed_screen("pomodoro")
        self.call_after_refresh(self.update_status)

    def _mount_project_screens(self) -> None:
        controllers = self._task_management
        if controllers is None:
            raise RuntimeError("Task-management controllers are required in full mode.")
        snapshot = self._timer_controller.snapshot
        self.install_screen(MainScreen(snapshot, controllers.tasks), name="main")
        self.install_screen(AllTasksScreen(controllers.tasks), name="all_tasks")
        self.install_screen(ProjectFormScreen(controllers.projects), name="project")
        self._tick_timer = self.set_interval(1, self.on_tick)
        self.show_project_screen()

    def _refresh_main_screen_for_active_project(self) -> None:
        active_project = self.current_project
        if active_project is None:
            return
        main_screen = self.get_screen("main", MainScreen)
        main_screen.set_project(active_project.id, active_project.name)
        main_screen.refresh_tasks()
        self._timer_controller.publish_current()
        self.update_status()

    def _handle_task_form_result(self, saved_task_id: int | None) -> None:
        active_project = self.current_project
        if saved_task_id is None or active_project is None:
            return
        main_screen = self.get_screen("main", MainScreen)
        main_screen.refresh_tasks(selected_task_id=saved_task_id)
        self.update_status()

    def _timer_controls_enabled(self) -> bool:
        return self.pomodoro_only or self.current_project is not None

    def _sync_tick_timer(self) -> None:
        if self._tick_timer is None:
            return
        if self._timer_controller.running:
            self._tick_timer.resume()
        else:
            self._tick_timer.pause()

    def _get_timer_screen(self) -> MainScreen | PomodoroScreen:
        if self.pomodoro_only:
            return self.get_screen("pomodoro", PomodoroScreen)
        return self.get_screen("main", MainScreen)

    def _show_installed_screen(self, screen_name: str) -> None:
        target_screen = self.get_screen(screen_name)
        if self.screen_stack and self.screen_stack[-1] is target_screen:
            return
        if len(self.screen_stack) <= 1:
            self.push_screen(screen_name)
            return
        self.switch_screen(screen_name)


__all__: list[str] = ["TickTask"]
