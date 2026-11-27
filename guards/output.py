"""Output guards G9 (numbers) and G10 (quotes). Pure code, no network.

G9:  a number in a model-written claim that is not in the brief or a code/tool result is
     re-tagged TO CONFIRM (origin `assumption`) and flagged.
G10: a FROM BRIEF claim or a Business Analyst signal needs a quote that really is in the brief;
     a claim without one is re-tagged TO CONFIRM, a signal without one is dropped.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import config
from schemas.case_file import Signal
from schemas.claims import Claim

TO_CONFIRM_ORIGIN = "assumption"
QUOTE_EDGE_CHARS = " \t\n.,;:!?\"'"
CHAR_FOLDS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
WHITESPACE = re.compile(r"\s+")
# A number not glued to a word, so ids such as C7 or O3 are not read as numbers.
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class GuardResult:
    claims: list[Claim]
    flagged_ids: list[str]


def normalize_for_match(text: str) -> str:
    return WHITESPACE.sub(" ", text.translate(CHAR_FOLDS)).casefold().strip()


def contains_quote(quote: str | None, source: str) -> bool:
    """True when the quote appears in the source, ignoring case and spacing."""
    needle = normalize_for_match(quote or "").strip(QUOTE_EDGE_CHARS)
    return bool(needle) and needle in normalize_for_match(source)


def to_confirm(claim: Claim) -> Claim:
    return claim.model_copy(update={"origin": TO_CONFIRM_ORIGIN, "quote": None})


def quote_guard(claims: list[Claim], brief: str) -> GuardResult:
    checked: list[Claim] = []
    flagged: list[str] = []
    for claim in claims:
        if claim.origin == "brief" and not contains_quote(claim.quote, brief):
            checked.append(to_confirm(claim))
            flagged.append(claim.id)
        else:
            checked.append(claim)
    return GuardResult(checked, flagged)


def split_signals(signals: list[Signal], brief: str) -> tuple[list[Signal], list[Signal]]:
    """Return (kept, dropped); a dropped signal is shown on screen as ignored."""
    kept = [s for s in signals if contains_quote(s.quote, brief)]
    dropped = [s for s in signals if not contains_quote(s.quote, brief)]
    return kept, dropped


def numbers_in(text: str) -> set[float]:
    return {round(float(m.replace(",", "")), config.MONEY_DECIMALS) for m in NUMBER.findall(text)}


def numbers_in_value(value: Any) -> set[float]:  # noqa: ANN401 - tool results are any JSON
    if isinstance(value, bool):
        return set()
    if isinstance(value, int | float):
        return {round(float(value), config.MONEY_DECIMALS)}
    if isinstance(value, str):
        return numbers_in(value)
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*(numbers_in_value(v) for v in value))
    return set()


def known_numbers(
    brief: str, tool_results: Iterable[Any], extra: Iterable[float] = ()
) -> set[float]:
    found = numbers_in(brief) | numbers_in_value(list(tool_results))
    return found | {round(float(x), config.MONEY_DECIMALS) for x in extra}


def number_guard(claims: list[Claim], known: set[float]) -> GuardResult:
    """Locked (calculated) claims are rebuilt by code, so only model-written claims are checked."""
    checked: list[Claim] = []
    flagged: list[str] = []
    for claim in claims:
        if not claim.locked and not numbers_in(claim.text) <= known:
            checked.append(to_confirm(claim))
            flagged.append(claim.id)
        else:
            checked.append(claim)
    return GuardResult(checked, flagged)
