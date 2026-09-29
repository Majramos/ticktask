from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from ticktask.infrastructure import Database


@pytest.fixture
def make_database(tmp_path: Path) -> Iterator[Callable[[str], Database]]:
    with ExitStack() as stack:

        def _create(name: str = "ticktask.db") -> Database:
            return stack.enter_context(Database(tmp_path / name))

        yield _create
