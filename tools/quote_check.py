"""Quote checker tool: does a quoted phrase really appear in the brief? Pure code, cannot fail."""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from guards.output import contains_quote

if TYPE_CHECKING:
    from tools.registry import ToolContext

NAME = "quote_checker"

SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Check that an exact phrase appears in the client brief (case and spacing are ignored)."
        ),
        "parameters": {
            "type": "object",
            "properties": {"quote": {"type": "string", "description": "The exact phrase"}},
            "required": ["quote"],
        },
    },
}


class QuoteInput(BaseModel):
    quote: str


def handle(request: QuoteInput, context: "ToolContext") -> dict[str, Any]:
    return {"found": contains_quote(request.quote, context.brief)}
