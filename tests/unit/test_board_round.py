from typing import Any

from domain.board_round import (
    answered_count,
    build_round,
    not_reviewed,
    replace_seat,
    review_gate,
    review_scoring,
)
from domain.gates import match_items
from domain.seats import SEATS_BY_ID
from domain.tracker import add_items, gate_drafts, next_tracker_id, scoring_drafts
from schemas.answers import (
    ChecklistAnswer,
    GateObjection,
    GateSeatAnswer,
    ScoringObjection,
    ScoringSeatAnswer,
)
from schemas.board import PlannedSeat, SeatResult
from schemas.state import TrackerItem

CLAIM_IDS = {f"C{i}" for i in range(1, 25)}


def seat(seat_id: str, title: str | None = None) -> PlannedSeat:
    spec = SEATS_BY_ID[seat_id]
    return PlannedSeat(id=seat_id, kind=spec.kind, title=title or spec.title, why="w")


def scoring_answer(
    ratings: dict[str, float], objections: list[dict[str, Any]] | None = None, **extra: object
) -> ScoringSeatAnswer:
    return ScoringSeatAnswer.model_validate(
        {
            "ratings": [{"criterion": k, "rating": v, "reason": "r"} for k, v in ratings.items()],
            "objections": objections or [],
            "quote": "q",
        }
        | extra
    )


def gate_answer(
    statuses: dict[str, str], objections: list[dict[str, Any]] | None = None
) -> GateSeatAnswer:
    return GateSeatAnswer.model_validate(
        {
            "items": [{"id": k, "status": v, "reason": "r"} for k, v in statuses.items()],
            "objections": objections or [],
            "quote": "q",
        }
    )


def northwind_round_one() -> tuple[list[SeatResult], list[TrackerItem]]:
    """The design screen's round 1, recomputed by code."""
    tracker: list[TrackerItem] = []
    results = []
    cfo, tracker = review_scoring(
        seat("cfo"),
        scoring_answer(
            {"cost_clarity": 7, "value": 5, "budget_fit": 3},
            [{"claim_id": "C7", "text": "No smaller first step", "severity": "blocker"}],
        ),
        CLAIM_IDS,
        tracker,
        1,
    )
    architect, tracker = review_scoring(
        seat("enterprise_architect"),
        scoring_answer(
            {"system_fit": 7, "risk_recovery": 4, "maintainability": 8},
            [
                {"claim_id": "C5", "text": "Protect the claims system"},
                {"claim_id": "C99", "text": "No rollback plan"},
            ],
        ),
        CLAIM_IDS,
        tracker,
        1,
    )
    vp, tracker = review_scoring(
        seat("vp_director", "VP, Claims Operations"),
        scoring_answer(
            {"customer_benefit": 9, "timing": 5, "disruption": 7},
            [
                {
                    "claim_id": "C16",
                    "text": "Go-live lands in the January peak",
                    "severity": "condition",
                }
            ],
        ),
        CLAIM_IDS,
        tracker,
        1,
    )
    procurement, tracker = review_gate(
        seat("procurement"),
        gate_answer(
            {"pricing_model": "met", "change_control": "partly", "acceptance_payment": "partly"},
            [{"item_id": "change_control", "text": "No change control process"}],
        ),
        tracker,
        1,
    )
    security, tracker = review_gate(
        seat("security"),
        gate_answer(
            {"data_protection": "partly", "access_control": "not_met", "data_rules_fit": "partly"},
            [{"item_id": "data_rules_fit", "text": "Retention rule unknown", "needs_client": True}],
        ),
        tracker,
        1,
    )
    results = [cfo, architect, vp, procurement, security]
    return results, tracker


# --- A whole round ---


def test_northwind_round_one_matches_the_design_numbers() -> None:
    results, _ = northwind_round_one()
    summary = [(r.seat_id, r.score, r.vote, r.outcome, r.able) for r in results]
    assert summary == [
        ("cfo", 5.3, "rejected", None, False),  # 2.80 + 1.75 + 0.75
        ("enterprise_architect", 6.2, "rejected", None, False),  # 2.80 + 1.40 + 2.00
        ("vp_director", 7.1, "yes_with_condition", None, True),  # 3.60 + 1.75 + 1.75
        ("procurement", None, None, "pass_with_conditions", True),
        ("security", None, None, "blocked", False),
    ]
    board = build_round(1, results)
    assert (board.progress.able, board.progress.total) == (2, 5)


def test_tracker_ids_kinds_severities_and_claim_ids() -> None:
    _, tracker = northwind_round_one()
    rows = [(t.id, t.seat, t.kind, t.severity, t.claim_ids, t.text) for t in tracker]
    assert rows == [
        ("O1", "cfo", "O", "blocker", ["C7"], "No smaller first step"),
        ("O2", "enterprise_architect", "O", "blocker", ["C5"], "Protect the claims system"),
        ("O3", "enterprise_architect", "O", "blocker", [], "No rollback plan"),  # C99 dropped
        ("O4", "vp_director", "O", "condition", ["C16"], "Go-live lands in the January peak"),
        ("O5", "procurement", "O", "condition", [], "No change control process"),
        ("O6", "procurement", "O", "condition", [], "Acceptance and payment terms: partly met."),
        ("O7", "security", "O", "condition", [], "Data protection: partly met."),
        ("O8", "security", "O", "blocker", [], "Access control: not met."),
        ("C1", "security", "C", "condition", [], "Retention rule unknown"),
    ]
    assert all(t.status == "open" and t.raised_round == 1 for t in tracker)


# --- Scoring seat rules ---


def test_passing_score_with_nothing_open_is_approved() -> None:
    result, tracker = review_scoring(
        seat("cfo"),
        scoring_answer({"cost_clarity": 8, "value": 8, "budget_fit": 8}),
        CLAIM_IDS,
        [],
        1,
    )
    assert (result.score, result.vote, result.able, tracker) == (8.0, "approved", True, [])


def test_a_stated_condition_alone_gives_yes_with_a_condition() -> None:
    answer = scoring_answer(
        {"cost_clarity": 8, "value": 8, "budget_fit": 8}, condition="Phase 2 funding"
    )
    result, _ = review_scoring(seat("cfo"), answer, CLAIM_IDS, [], 1)
    assert (result.vote, result.condition) == ("yes_with_condition", "Phase 2 funding")


def test_an_open_blocker_on_a_passing_score_is_not_approved() -> None:
    answer = scoring_answer(
        {"cost_clarity": 9, "value": 9, "budget_fit": 9},
        [{"text": "Rollback missing", "severity": "blocker"}],
    )
    result, _ = review_scoring(seat("cfo"), answer, CLAIM_IDS, [], 1)
    assert result.vote == "yes_with_condition"


def test_a_missing_criterion_marks_the_seat_partial_and_counts_zero() -> None:
    result, _ = review_scoring(
        seat("cfo"), scoring_answer({"cost_clarity": 10, "value": 10}), CLAIM_IDS, [], 1
    )
    assert (result.partial, result.score, result.vote) == (True, 7.5, "approved")


def test_clamped_ratings_flow_into_the_seat_result() -> None:
    result, _ = review_scoring(
        seat("cfo"),
        scoring_answer({"cost_clarity": 15, "value": -2, "budget_fit": 10}),
        CLAIM_IDS,
        [],
        1,
    )
    assert [c.rating for c in result.criteria] == [10, 0, 10]
    assert result.score == 6.5


def test_needs_client_objections_become_c_items_with_their_own_numbering() -> None:
    drafts = scoring_drafts(
        "cfo",
        [
            ScoringObjection(text="Phase 2 funding", severity="condition", needs_client=True),
            ScoringObjection(text="  "),
            ScoringObjection(text="Cost split", claim_id="C3"),
        ],
        CLAIM_IDS,
    )
    tracker = add_items([], drafts, 1)
    assert [(t.id, t.kind) for t in tracker] == [("C1", "C"), ("O1", "O")]  # empty text dropped
    assert next_tracker_id(tracker, "O") == "O2" and next_tracker_id(tracker, "C") == "C2"


# --- Gate seat rules ---


def test_gate_objections_on_met_or_unknown_items_are_ignored() -> None:
    items = match_items(
        SEATS_BY_ID["procurement"],
        [
            ChecklistAnswer(id="pricing_model", status="met"),
            ChecklistAnswer(id="change_control", status="met"),
            ChecklistAnswer(id="acceptance_payment", status="met"),
        ],
    )
    objections = [
        GateObjection(item_id="pricing_model", text="x"),
        GateObjection(item_id="vibes", text="y"),
    ]
    assert gate_drafts("procurement", items, objections) == []


def test_a_missing_gate_item_becomes_a_blocker_item_and_a_partial_answer() -> None:
    result, tracker = review_gate(
        seat("procurement"),
        gate_answer({"pricing_model": "met", "acceptance_payment": "met"}),
        [],
        1,
    )
    assert (result.outcome, result.partial, result.able) == ("blocked", True, False)
    assert [(t.item_id, t.severity, t.text) for t in tracker] == [
        ("change_control", "blocker", "Change control: not met.")
    ]


# --- Not reviewed and retry ---


def test_a_failed_seat_is_not_reviewed_and_cannot_proceed() -> None:
    result = not_reviewed(seat("enterprise_architect"))
    assert (result.status, result.able, result.score, result.vote, result.needed) == (
        "not_reviewed",
        False,
        None,
        None,
        8.0,
    )


def test_one_failed_seat_does_not_hide_the_others() -> None:
    results, _ = northwind_round_one()
    results[4] = not_reviewed(seat("security"))
    board = build_round(1, results)
    assert (board.progress.able, board.progress.total) == (2, 5)
    assert answered_count(results) == 4
    assert [r.vote for r in results[:3]] == ["rejected", "rejected", "yes_with_condition"]


def test_retrying_a_seat_recomputes_the_round() -> None:
    results, tracker = northwind_round_one()
    # A seat that failed never added tracker items, so drop the VP's from the setup.
    tracker = [t for t in tracker if t.seat != "vp_director"]
    results[2] = not_reviewed(seat("vp_director", "VP, Claims Operations"))
    board = build_round(1, results)
    assert board.progress.able == 1
    retried, tracker = review_scoring(
        seat("vp_director", "VP, Claims Operations"),
        scoring_answer({"customer_benefit": 9, "timing": 8, "disruption": 8}),
        CLAIM_IDS,
        tracker,
        1,
    )
    board = replace_seat(board, retried)
    assert board.seats[2].vote == "approved"
    assert (board.progress.able, board.progress.total) == (2, 5)
    assert [s.seat_id for s in board.seats] == [
        "cfo",
        "enterprise_architect",
        "vp_director",
        "procurement",
        "security",
    ]
