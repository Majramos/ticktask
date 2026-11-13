"""Tests for the project application service."""

import pytest

from tests.fakes import InMemoryStore, InMemoryUnitOfWorkFactory, create_services
from ticktask.application.exceptions import ProjectNameConflictError
from ticktask.application.projects import ProjectService


def test_list_projects_returns_projects_sorted_by_id() -> None:
    project_service, _, _ = create_services()
    project_service.create_project("Beta")
    project_service.create_project("Alpha")

    projects = project_service.list_projects()

    assert [project.name for project in projects] == ["Beta", "Alpha"]
    assert [project.id for project in projects] == [1, 2]


def test_list_projects_returns_empty_list_without_projects() -> None:
    project_service, _, _ = create_services()

    assert project_service.list_projects() == []


def test_get_project_returns_project_and_none_when_missing() -> None:
    project_service, _, _ = create_services()
    created = project_service.create_project("Inbox")

    assert project_service.get_project(created.id) == created
    assert project_service.get_project(999) is None


def test_get_project_by_name_normalizes_input() -> None:
    project_service, _, _ = create_services()
    created = project_service.create_project("Inbox")

    assert project_service.get_project_by_name("  Inbox ") == created
    assert project_service.get_project_by_name("InboxX") is None


def test_create_project_persists_validated_project() -> None:
    project_service, _, factory = create_services()

    project = project_service.create_project("  Inbox  ")

    assert project.name == "Inbox"
    assert factory.store.projects[project.id] == project


def test_create_project_rejects_duplicate_name() -> None:
    project_service, _, _ = create_services()
    project_service.create_project("Inbox")

    with pytest.raises(ProjectNameConflictError, match="already exists"):
        project_service.create_project("Inbox")


@pytest.mark.parametrize("name", ["   ", ""])
def test_create_project_validates_name_before_transaction(name: str) -> None:
    project_service, _, factory = create_services()

    with pytest.raises(ValueError, match="cannot be empty"):
        project_service.create_project(name)

    assert factory.store.projects == {}


def test_service_writes_through_shared_store() -> None:
    store = InMemoryStore()
    service = ProjectService(InMemoryUnitOfWorkFactory(store))

    created = service.create_project("Inbox")

    assert store.projects[created.id] == created
