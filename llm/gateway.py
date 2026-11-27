"""The real model behind run_agent: an OpenAI-compatible gateway (LiteLLM, or Gemini on the laptop).

Errors are classified for the retry policy. Exception text is never passed on: it can hold
addresses or key fragments (guard G11).
"""

import os
from typing import Any

import openai
from openai import AsyncOpenAI

import config
from domain.errors import BudgetUsedUp
from llm.client import ChatReply, ChatRequest, ErrorKind, ModelCallError, ToolCall

NOT_CONFIGURED = "Live runs are not available right now. The sample run is still available."
BUDGET_WORDS = ("budget", "spend", "credit")
AUTH_STATUSES = (401, 403)
PAYMENT_STATUS = 402
RATE_LIMIT_STATUS = 429
BAD_REQUEST_STATUSES = (400, 404, 422)


def classify_status(status: int, message: str) -> ErrorKind:
    if any(word in message.lower() for word in BUDGET_WORDS) or status == PAYMENT_STATUS:
        return "budget"
    if status in AUTH_STATUSES:
        return "auth"
    if status == RATE_LIMIT_STATUS:
        return "rate_limit"
    if status in BAD_REQUEST_STATUSES:
        return "bad_request"
    return "server"


def to_reply(response: Any) -> ChatReply:  # noqa: ANN401 - the SDK's response object
    choice = response.choices[0]
    message = choice.message
    calls = [
        ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
        for c in message.tool_calls or []
    ]
    usage = response.usage
    return ChatReply(
        content=message.content or "",
        tool_calls=calls,
        finish_reason=choice.finish_reason,
        tokens_in=(usage.prompt_tokens or 0) if usage else 0,
        tokens_out=(usage.completion_tokens or 0) if usage else 0,
        # Kept whole so provider-specific fields (such as reasoning signatures) go back unchanged.
        assistant_message=message.model_dump(exclude_none=True),
        model=response.model or "",
    )


class GatewayModel:
    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "GatewayModel":
        """Refuses to start without settings, so no request ever goes to a default address."""
        base_url = os.getenv(config.LLM_BASE_URL_VAR)
        api_key = os.getenv(config.LLM_API_KEY_VAR)
        if not base_url or not api_key:
            raise BudgetUsedUp(NOT_CONFIGURED)
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=config.LLM_TIMEOUT_S,
            max_retries=0,  # run_agent owns the retry policy
        )
        return cls(client)

    async def complete(self, request: ChatRequest) -> ChatReply:
        options: dict[str, Any] = {}
        if request.tools:
            options.update(tools=request.tools, tool_choice="auto")
        if request.json_mode:
            options["response_format"] = {"type": "json_object"}
        try:
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=request.messages,
                max_tokens=request.max_tokens,
                **options,
            )
        except openai.APITimeoutError:
            raise ModelCallError("timeout") from None
        except openai.APIStatusError as error:
            raise ModelCallError(classify_status(error.status_code, str(error.message))) from None
        except openai.APIConnectionError:
            raise ModelCallError("server") from None
        return to_reply(response)
