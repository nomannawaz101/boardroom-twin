"""The verdict order of plan section 4.7: a known Rejected or Blocked always wins."""

import pytest

from domain.loop import final_verdict
from schemas.board import BoardRound, Progress, SeatResult
from schemas.state import TrackerItem


def seat(seat_id: str, **fields: object) -> SeatResult:
    base: dict[str, object] = {
        "seat_id": seat_id,
        "kind": "scoring",
        "title": seat_id,
        "status": "answered",
        "able": True,
    }
    return SeatResult.model_validate(base | fields)


APPROVED = {"vote": "approved"}
CONDITION = {"vote": "yes_with_condition"}
REJECTED = {"vote": "rejected", "able": False}
PASS = {"kind": "gate", "outcome": "pass"}
PASS_COND = {"kind": "gate", "outcome": "pass_with_conditions"}
BLOCKED = {"kind": "gate", "outcome": "blocked", "able": False}
NOT_REVIEWED = {"status": "not_reviewed", "able": False}
PARTIAL_GATE = {"kind": "gate", "status": "not_reviewed", "able": False, "partial": True}
OPEN_ITEM = TrackerItem(id="C1", seat="cfo", kind="C", text="Phase 2 funding", raised_round=1)


def verdict(*seats: dict[str, object], tracker: list[TrackerItem] | None = None) -> str:
    results = [seat(f"s{i}", **fields) for i, fields in enumerate(seats)]
    board = BoardRound(no=1, seats=results, progress=Progress(able=0, total=len(results)))
    return final_verdict(board, tracker or []).label


@pytest.mark.parametrize(
    ("seats", "expected"),
    [
        ((APPROVED, PASS), "Approved"),
        ((APPROVED, PASS_COND), "Approved with conditions"),
        ((CONDITION, PASS), "Approved with conditions"),
        ((REJECTED, PASS), "Not ready yet"),
        ((APPROVED, BLOCKED), "Not ready yet"),
        ((APPROVED, NOT_REVIEWED), "Review incomplete"),
        ((APPROVED, PARTIAL_GATE), "Review incomplete"),
        # A known result wins over a failed call (F1 and F3 of Appendix B).
        ((REJECTED, NOT_REVIEWED), "Not ready yet"),
        ((BLOCKED, NOT_REVIEWED, APPROVED), "Not ready yet"),
        ((PARTIAL_GATE, REJECTED), "Not ready yet"),
    ],
)
def test_verdict_order(seats: tuple[dict[str, object], ...], expected: str) -> None:
    assert verdict(*seats) == expected


def test_an_open_item_alone_gives_approved_with_conditions() -> None:
    assert verdict(APPROVED, PASS, tracker=[OPEN_ITEM]) == "Approved with conditions"


def test_a_fixed_item_no_longer_holds_the_verdict_back() -> None:
    fixed = OPEN_ITEM.model_copy(update={"status": "fixed"})
    assert verdict(APPROVED, PASS, tracker=[fixed]) == "Approved"
