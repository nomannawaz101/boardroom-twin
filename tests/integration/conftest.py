"""Shared fixture: the scripted fake model in place of the live one, and no real waits."""

from collections.abc import Iterator

import pytest

from app import app
from llm.client import Runtime
from llm.fake import FakeChatModel, FakeStep
from services import runtime as wiring


class Scripted:
    def __init__(self) -> None:
        self.model = FakeChatModel([])

    def load(self, script: list[FakeStep]) -> FakeChatModel:
        self.model = FakeChatModel(script)
        return self.model


async def no_wait(seconds: float) -> None:
    return None


@pytest.fixture
def scripted() -> Iterator[Scripted]:
    holder = Scripted()
    app.dependency_overrides[wiring.make_runtime] = lambda: Runtime(
        model=holder.model, sleep=no_wait
    )
    yield holder
    app.dependency_overrides.clear()
