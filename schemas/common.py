import re
from typing import Any

from pydantic import AfterValidator, BeforeValidator, ValidationInfo

# run_agent validates a model's reply with this context key set. Count and length rules apply
# only then, so code-built objects and the run state (including a safe default) stay valid.
FROM_MODEL = "from_model"
# run_agent also passes this key for a gate seat: the checklist the answer must cover.
REQUIRED_ITEMS = "required_items"
NOT_WORD = re.compile(r"[^a-z0-9]+")


def capped(limit: int) -> BeforeValidator:
    """Cut an over-long list from a model instead of failing the whole answer (plan section 7.2).

    A null list means "nothing", so it becomes an empty list rather than a failed answer.
    """

    def cut(value: Any) -> Any:  # noqa: ANN401 - runs before pydantic knows the type
        if value is None:
            return []
        return value[:limit] if isinstance(value, list) else value

    return BeforeValidator(cut)


def none_if_not_in(allowed: tuple[str, ...]) -> BeforeValidator:
    """Map an unexpected enum value from a model to null (unclear) instead of failing."""

    def check(value: Any) -> Any:  # noqa: ANN401 - runs before pydantic knows the type
        return value if value in allowed else None

    return BeforeValidator(check)


def from_model(info: ValidationInfo) -> bool:
    return bool((info.context or {}).get(FROM_MODEL))


def at_least(minimum: int) -> AfterValidator:
    """A model's answer with fewer items fails the check, so run_agent retries it."""

    def check(value: list[Any], info: ValidationInfo) -> list[Any]:
        if from_model(info) and len(value) < minimum:
            raise ValueError(f"needs at least {minimum} items, got {len(value)}")
        return value

    return AfterValidator(check)


def max_words(limit: int) -> AfterValidator:
    def check(value: str, info: ValidationInfo) -> str:
        if from_model(info) and len(value.split()) > limit:
            raise ValueError(f"must be at most {limit} words")
        return value

    return AfterValidator(check)


def match_key(text: str) -> str:
    """Match "cost_clarity", "Cost clarity" and "cost-clarity" to the same criterion or item."""
    return NOT_WORD.sub("_", text.lower()).strip("_")
