"""Scripted fake model: canned replies and failures, so every path is tested for free."""

import json
from collections import deque
from collections.abc import Iterable
from typing import Any

from llm.client import ChatReply, ChatRequest, ErrorKind, ModelCallError, ToolCall

FAKE_TOKENS_IN = 100
FAKE_TOKENS_OUT = 50

FakeStep = ChatReply | ModelCallError


class ScriptExhausted(Exception):
    """The test asked the fake model for more replies than it scripted."""


class FakeChatModel:
    def __init__(self, script: Iterable[FakeStep]) -> None:
        self._script = deque(script)
        self.requests: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> ChatReply:
        self.requests.append(request)
        if not self._script:
            raise ScriptExhausted()
        step = self._script.popleft()
        if isinstance(step, ModelCallError):
            raise step
        return step


def reply_text(text: str, finish_reason: str = "stop") -> ChatReply:
    return ChatReply(
        content=text,
        tool_calls=[],
        finish_reason=finish_reason,
        tokens_in=FAKE_TOKENS_IN,
        tokens_out=FAKE_TOKENS_OUT,
        assistant_message={"role": "assistant", "content": text},
    )


def reply_json(value: dict[str, Any]) -> ChatReply:
    return reply_text(json.dumps(value))


def reply_tool(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> ChatReply:
    call = ToolCall(id=call_id, name=name, arguments=json.dumps(arguments))
    message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": call.arguments},
            }
        ],
    }
    return ChatReply(
        content="",
        tool_calls=[call],
        finish_reason="tool_calls",
        tokens_in=FAKE_TOKENS_IN,
        tokens_out=FAKE_TOKENS_OUT,
        assistant_message=message,
    )


def fail(kind: ErrorKind) -> ModelCallError:
    return ModelCallError(kind)
