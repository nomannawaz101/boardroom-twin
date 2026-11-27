import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from openai.types.chat import ChatCompletion

from llm.client import ChatRequest
from llm.gateway import GatewayModel, classify_status, to_reply


def completion(message: dict[str, Any], finish_reason: str = "stop") -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
        }
    )


@pytest.mark.parametrize(
    ("status", "message", "kind"),
    [
        (429, "Too many requests", "rate_limit"),
        (400, "Budget has been exceeded for this key", "budget"),
        (402, "Payment required", "budget"),
        (401, "Invalid key", "auth"),
        (403, "Forbidden", "auth"),
        (400, "Bad request", "bad_request"),
        (500, "Internal error", "server"),
        (503, "Unavailable", "server"),
    ],
)
def test_classify_status(status: int, message: str, kind: str) -> None:
    assert classify_status(status, message) == kind


def test_text_reply_is_converted() -> None:
    reply = to_reply(completion({"role": "assistant", "content": '{"a": 1}'}))
    assert (reply.content, reply.tool_calls, reply.finish_reason) == ('{"a": 1}', [], "stop")
    assert (reply.tokens_in, reply.tokens_out) == (12, 3)


def test_tool_call_reply_keeps_the_assistant_message_whole() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "working_days", "arguments": '{"start": "2026-12-07"}'},
            }
        ],
    }
    reply = to_reply(completion(message, "tool_calls"))
    assert reply.content == ""
    assert (reply.tool_calls[0].id, reply.tool_calls[0].name) == ("c1", "working_days")
    assert reply.assistant_message["tool_calls"][0]["id"] == "c1"


def test_request_options_follow_tools_and_json_mode() -> None:
    sent: dict[str, Any] = {}

    async def create(**kwargs: Any) -> ChatCompletion:  # noqa: ANN401
        sent.update(kwargs)
        return completion({"role": "assistant", "content": "{}"})

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    model = GatewayModel(client)  # type: ignore[arg-type]
    request = ChatRequest(model="m", messages=[], max_tokens=50, tools=None, json_mode=True)
    asyncio.run(model.complete(request))
    assert sent["response_format"] == {"type": "json_object"}
    assert "tools" not in sent and sent["max_tokens"] == 50
