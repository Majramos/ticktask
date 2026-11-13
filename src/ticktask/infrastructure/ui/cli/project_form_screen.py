"""Project selection and creation screen."""

from __future__ import annotations

from typing import ClassVar, Protocol, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Select, Static

from ticktask.adapters.controllers import ProjectController
from ticktask.domain.projects import PROJECT_NAME_MAX_LENGTH, Project


class _ContinueProjectScreen(Protocol):
    def action_continue_project(self) -> None: ...


class _ActivateProjectApp(Protocol):
    def activate_project(self, project: Project) -> None: ...


class ExistingProjectSelect(Select[int]):
    """Select that uses Enter to continue when the menu is collapsed."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("enter", "continue_project", "Continue", show=False),
        Binding("down, space, up", "show_overlay", "Show-menu", show=False),
    ]

    def action_continue_project(self) -> None:
        cast(_ContinueProjectScreen, self.screen).action_continue_project()


class ProjectFormScreen(Screen[str | None]):
    """Project selection and creation flow."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("enter", "continue_project", "Continue")
    ]

    def __init__(self, project_controller: ProjectController) -> None:
        super().__init__()
        self._project_controller: ProjectController = project_controller
        self.projects: list[Project] = []
        self.error_message: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Container(
                Static("Choose or create a project", id="project-setup-title"),
                Static("Existing projects", classes="project-setup-label"),
                ExistingProjectSelect(
                    [],
                    prompt="Select a project",
                    allow_blank=True,
                    id="existing-project-select",
                ),
                Static("Create a new project", classes="project-setup-label"),
                Input(
                    placeholder="Enter a new project name",
                    max_length=PROJECT_NAME_MAX_LENGTH,
                    id="new-project-input",
                ),
                Button("Continue", id="project-continue"),
                Static("", id="project-setup-error"),
                id="project-setup",
            ),
            id="project-form-screen",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._apply_projects()

    def on_show(self) -> None:
        self._apply_projects()

    def action_continue_project(self) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "project-continue":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-project-input":
            self._submit()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "existing-project-select" and event.value != Select.BLANK:
            self._set_error("")

    def refresh_projects(self) -> None:
        """Load and render available projects."""
        self.projects = self._project_controller.list_projects()
        self.error_message = (
            "Create your first project to get started." if not self.projects else ""
        )
        self._apply_projects()

    def _set_error(self, message: str) -> None:
        """Set the project form error message."""
        self.error_message = message
        if self._has_dom():
            self.query_one("#project-setup-error", Static).update(message)

    def _submit(self) -> None:
        new_name = self.query_one("#new-project-input", Input).value.strip()
        if new_name:
            self._create_and_activate_project(new_name)
            return

        selected_project = self._selected_project()
        if selected_project is not None:
            self._activate_project(selected_project)
            return

        self._set_error("Select an existing project or enter a new project name.")

    def _create_and_activate_project(self, name: str) -> None:
        try:
            project = self._project_controller.create_project(name)
        except ValueError as error:
            self._set_error(str(error))
            return
        self._activate_project(project)

    def _selected_project(self) -> Project | None:
        project_id = self.query_one("#existing-project-select", Select).value
        if not isinstance(project_id, int):
            return None
        return self._find_selected_project(project_id)

    def _apply_projects(self) -> None:
        if not self._has_dom():
            return
        select_widget = self.query_one("#existing-project-select", Select)
        select_widget.set_options(
            [(project.name, project.id) for project in self.projects]
        )
        if len(self.projects) == 1:
            select_widget.value = self.projects[0].id
        else:
            select_widget.clear()
        self.query_one("#new-project-input", Input).value = ""
        self.query_one("#project-setup-error", Static).update(self.error_message)

    def _find_selected_project(self, project_id: int) -> Project | None:
        return next(
            (project for project in self.projects if project.id == project_id), None
        ) or self._project_controller.get_project(project_id)

    def _activate_project(self, project: Project) -> None:
        cast(_ActivateProjectApp, self.app).activate_project(project)

    def _has_dom(self) -> bool:
        return self.is_mounted


__all__: list[str] = ["ExistingProjectSelect", "ProjectFormScreen"]
