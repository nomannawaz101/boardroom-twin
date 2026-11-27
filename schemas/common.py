from typing import Any

from pydantic import BeforeValidator


def capped(limit: int) -> BeforeValidator:
    """Cut an over-long list from a model instead of failing the whole answer (plan section 7.2)."""

    def cut(value: Any) -> Any:  # noqa: ANN401 - runs before pydantic knows the type
        return value[:limit] if isinstance(value, list) else value

    return BeforeValidator(cut)


def none_if_not_in(allowed: tuple[str, ...]) -> BeforeValidator:
    """Map an unexpected enum value from a model to null (unclear) instead of failing."""

    def check(value: Any) -> Any:  # noqa: ANN401 - runs before pydantic knows the type
        return value if value in allowed else None

    return BeforeValidator(check)
