"""Pilot tests for Textual UI screens and navigation."""

from __future__ import annotations

import pytest
from textual.widgets import Input, Select, Static, TextArea

from tests.fakes import create_services
from ticktask.adapters.controllers import TaskController, TaskManagementControllers
from ticktask.adapters.controllers.projects import ProjectController
from ticktask.application.publishers import NoOpTimerStatePublisher
from ticktask.application.timers import PomodoroController
from ticktask.domain.tasks import TaskPriority
from ticktask.domain.timer import TimerKind, TimerSpec
from ticktask.infrastructure.ui.cli import TickTask
from ticktask.infrastructure.ui.cli.all_tasks_screen import AllTasksScreen
from ticktask.infrastructure.ui.cli.main_screen import MainScreen, PomodoroScreen
from ticktask.infrastructure.ui.cli.project_form_screen import ProjectFormScreen
from ticktask.infrastructure.ui.cli.task_form_screen import (
    TaskDescriptionTextArea,
    TaskFormScreen,
)
from ticktask.infrastructure.ui.cli.timer_widgets import TimerCard, TimerCarousel


def pomodoro_controller(clock_state: list[float] | None = None) -> PomodoroController:
    clock_state = [0.0] if clock_state is None else clock_state
    return PomodoroController(
        [
            TimerSpec(TimerKind.FOCUS, 25),
            TimerSpec(TimerKind.SHORT_BREAK, 5),
            TimerSpec(TimerKind.LONG_BREAK, 10),
        ],
        NoOpTimerStatePublisher(),
        clock=lambda: clock_state[0],
    )


def task_management() -> tuple[
    TaskManagementControllers, ProjectController, TaskController
]:
    project_service, task_service, _ = create_services()
    projects = ProjectController(project_service)
    tasks = TaskController(task_service)
    return TaskManagementControllers(projects=projects, tasks=tasks), projects, tasks


@pytest.mark.asyncio
async def test_pomodoro_only_app_mounts_and_controls_timer() -> None:
    clock = [0.0]
    controller = pomodoro_controller(clock)
    app = TickTask(controller, None)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PomodoroScreen)
        assert app.pomodoro_only is True

        await pilot.press("space")
        await pilot.pause()
        assert controller.running is True

        await pilot.press("a")
        await pilot.pause()
        assert controller.snapshot.auto_start is False

        await pilot.press("right")
        await pilot.pause()
        assert controller.snapshot.current_index == 1

        await pilot.press("r")
        await pilot.pause()
        assert controller.snapshot.remaining_seconds == 5

        await pilot.press("space")
        await pilot.pause()
        assert controller.running is False

        status = app.screen.query_one("#status", Static).content
        assert "Paused" in str(status)


@pytest.mark.asyncio
async def test_pomodoro_app_tick_advances_on_completion() -> None:
    clock = [0.0]
    controller = pomodoro_controller(clock)
    app = TickTask(controller, None)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        controller.toggle_run()
        clock[0] += 30
        app.on_tick()
        await pilot.pause()
        assert controller.snapshot.current_index == 1


@pytest.mark.asyncio
async def test_timer_carousel_and_cards_render_snapshot() -> None:
    controller = pomodoro_controller()
    app = TickTask(controller, None)

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        carousel = app.screen.query_one(TimerCarousel)
        center = app.screen.query_one("#timer-slot-0", TimerCard)
        left = app.screen.query_one("#timer-slot-neg-1", TimerCard)

        assert "current" in center.classes
        assert "past" in left.classes
        assert "slot-center" in center.classes
        assert "slot-side" in left.classes
        assert carousel.slot_id(-2) == "timer-slot-neg-2"
        assert carousel.slot_id(1) == "timer-slot-1"

        controller.advance()
        app.update_status()
        await pilot.pause()
        assert carousel._rendered_snapshot is not None
        assert carousel._rendered_snapshot.current_index == 1


@pytest.mark.asyncio
async def test_project_form_validates_and_creates_project() -> None:
    controllers, projects, _ = task_management()
    app = TickTask(pomodoro_controller(), controllers)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ProjectFormScreen)

        await pilot.press("enter")
        await pilot.pause()
        error = app.screen.query_one("#project-setup-error", Static).content
        assert "Select an existing project" in str(error)

        name_input = app.screen.query_one("#new-project-input", Input)
        name_input.value = "Inbox"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.current_project is not None
        assert app.current_project.name == "Inbox"
        assert projects.list_projects()[0].name == "Inbox"


@pytest.mark.asyncio
async def test_project_form_selects_existing_project() -> None:
    controllers, projects, _ = task_management()
    created = projects.create_project("Alpha")
    projects.create_project("Beta")
    app = TickTask(pomodoro_controller(), controllers)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        select = app.screen.query_one("#existing-project-select", Select)
        select.value = created.id
        await pilot.click("#project-continue")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.current_project is not None
        assert app.current_project.id == created.id


@pytest.mark.asyncio
async def test_main_screen_task_lifecycle_and_navigation() -> None:
    controllers, projects, tasks = task_management()
    project = projects.create_project("Inbox")
    tasks.save_task(
        project.id,
        None,
        description="seed",
        priority=TaskPriority.MEDIUM,
        completed=False,
        archived=False,
    )
    app = TickTask(pomodoro_controller(), controllers)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        # Select the only project
        select = app.screen.query_one("#existing-project-select", Select)
        select.value = project.id
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

        main = app.screen
        main.refresh_tasks()
        await pilot.pause()
        listing = main.query_one("#tasks-list", Static).content
        assert "seed" in str(listing)

        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, TaskFormScreen)
        desc = app.screen.query_one("#task-description", TextArea)
        desc.load_text("new task")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        listing = app.screen.query_one("#tasks-list", Static).content
        assert "new task" in str(listing)

        await pilot.press("v")
        await pilot.pause()
        assert isinstance(app.screen, AllTasksScreen)
        all_listing = app.screen.query_one("#all-tasks-list", Static).content
        assert "new task" in str(all_listing)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ProjectFormScreen)
        assert app.current_project is None


@pytest.mark.asyncio
async def test_task_form_edit_shortcuts_and_validation() -> None:
    controllers, projects, tasks = task_management()
    project = projects.create_project("Inbox")
    seed = tasks.save_task(
        project.id,
        None,
        description="edit me",
        priority=TaskPriority.MEDIUM,
        completed=False,
        archived=False,
    )
    app = TickTask(pomodoro_controller(), controllers)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.screen.query_one("#existing-project-select", Select).value = project.id
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskFormScreen)
        assert app.screen._task_view is not None
        assert app.screen._task_view.id == seed.id

        app.screen.action_task_priority_high()
        app.screen.action_task_toggle_completed()
        app.screen.action_task_toggle_archived()
        await pilot.pause()
        widgets = app.screen._form_widgets()
        assert widgets.priority.value is TaskPriority.HIGH
        assert widgets.completed.value is True
        assert widgets.archived.value is True

        widgets.description.load_text("   ")
        await pilot.press("enter")
        await pilot.pause()
        error = app.screen.query_one("#task-form-error", Static).content
        assert "cannot be empty" in str(error)

        widgets.description.load_text("updated")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


@pytest.mark.asyncio
async def test_task_description_text_area_limits_and_newline() -> None:
    controllers, projects, _ = task_management()
    projects.create_project("Inbox")
    app = TickTask(pomodoro_controller(), controllers)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.screen.query_one("#existing-project-select", Select).value = 1
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()

        area = app.screen.query_one("#task-description", TaskDescriptionTextArea)
        area.load_text("x" * 300)
        assert len(area.text) == 256

        area.load_text("line")
        _start, _end = area.selection
        area.action_insert_newline()
        await pilot.pause()
        assert "\n" in area.text
        assert TaskFormScreen._task_description_wrap_width(area) >= 1


@pytest.mark.asyncio
async def test_project_change_pauses_running_timer() -> None:
    controllers, projects, _ = task_management()
    projects.create_project("Inbox")
    controller = pomodoro_controller()
    app = TickTask(controller, controllers)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.screen.query_one("#existing-project-select", Select).value = 1
        await pilot.press("enter")
        await pilot.pause()
        app.toggle_run()
        assert controller.running is True
        app.change_project()
        await pilot.pause()
        assert controller.running is False
        assert isinstance(app.screen, ProjectFormScreen)
