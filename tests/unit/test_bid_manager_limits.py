"""Phase 4 follow-up rules: the Bid Manager cannot change commercial facts, cannot skip an open
objection unnoticed, and client-only items and assumptions appear once."""

import pytest

from agents.bid_manager import REFUSALS, describe, merge_steps, missing_ids, order_open
from domain.claims import (
    HOLIDAYS_NOT_CHECKED,
    apply_change,
    assemble_claims,
    normalize_text,
    states_commercial_fact,
)
from domain.report import not_answered, open_conditions, seat_reason
from domain.revision import apply_bid_changes
from domain.tracker import ItemDraft, add_items
from schemas.answers import Change
from schemas.board import ChecklistResult, SeatResult
from schemas.claims import ASSUMPTION_PREFIX, Claim, DraftClaim
from schemas.revision import BidRound
from schemas.state import RunState, TrackerItem
from schemas.step import StepRecord

CLAIMS = [
    Claim(
        id="C1",
        section="client_situation",
        text="Claims staff answer status calls.",
        origin="brief",
    ),
    Claim(id="C2", section="proposed_solution", text="A read-only status page.", origin="proposal"),
    Claim(id="C3", section="scope", text="Time and materials, billed monthly.", origin="proposal"),
    Claim(id="C4", section="risks", text="The data feed may be late.", origin="proposal"),
    Claim(id="C5", section="team_cost", text="Total: $24,000.", origin="calculated", locked=True),
]


def change(action: str, claim_id: str | None = None, text: str = "", **extra: str) -> Change:
    return Change.model_validate(
        {"objection_id": "O1", "action": action, "claim_id": claim_id, "text": text} | extra
    )


def item(item_id: str, seat: str = "cfo", **fields: object) -> TrackerItem:
    base = {"id": item_id, "seat": seat, "kind": item_id[0], "text": f"{item_id} text"}
    return TrackerItem.model_validate(base | {"raised_round": 1} | fields)


# --- Fix 1: commercial facts change only through an assumption ---


@pytest.mark.parametrize(
    ("action", "claim_id"),
    [("replace", "C1"), ("remove", "C1"), ("replace", "C3"), ("remove", "C3")],
)
def test_brief_and_commercial_claims_cannot_be_replaced_or_removed(
    action: str, claim_id: str
) -> None:
    result = apply_change(CLAIMS, change(action, claim_id, "A fixed scope instead."))
    assert result.refused == "protected" and result.claims == CLAIMS


@pytest.mark.parametrize(
    "text",
    [
        "Lumen Works offers a fixed price of $24,000.",
        "A not-to-exceed cap on top of time and materials.",
        "Three engineers instead of two.",
        "Go-live moves to Jan 18.",
        "The rate drops to 550 per day.",
    ],
)
def test_a_statement_about_terms_people_or_dates_is_refused(text: str) -> None:
    assert apply_change(CLAIMS, change("replace", "C2", text)).refused == "protected"
    assert apply_change(CLAIMS, change("add", "C2", text)).refused == "protected"


def test_the_same_request_as_an_assumption_is_allowed() -> None:
    text = (
        "Confirm with the client: Lumen Works could offer a not-to-exceed cap of $24,000 "
        "on top of time and materials."
    )
    result = apply_change(CLAIMS, change("assume", None, text))
    assert result.refused is None
    added = result.claims[-1]
    assert (added.section, added.origin, added.text) == ("assumptions", "assumption", text)


def test_ordinary_proposal_text_can_still_change() -> None:
    result = apply_change(CLAIMS, change("replace", "C2", "A read-only page with a kill switch."))
    assert result.refused is None and result.claims[1].text.endswith("kill switch.")
    assert not states_commercial_fact("Acceptance: the client signs off each phase.")


def test_refusals_are_listed_in_words() -> None:
    claims, applied, _ = apply_bid_changes(
        CLAIMS, [item("O1")], [change("replace", "C3", "Fixed price instead.")], 1
    )
    assert claims == CLAIMS and applied[0].outcome == "protected"
    assert "protected" in REFUSALS and "duplicate" in REFUSALS


# --- Fix 2: an open objection is never skipped silently ---


def test_missing_objections_are_listed_blockers_first() -> None:
    open_items = [
        item("O1", severity="condition"),
        item("O2"),
        item("C1"),
        item("O3", severity="condition"),
        item("O4"),
    ]
    assert [t.id for t in order_open(open_items)] == ["O2", "C1", "O4", "O1", "O3"]
    answered = [change("replace", "C2", "x").model_copy(update={"objection_id": "O2"})]
    assert missing_ids(open_items, answered) == ["O4", "O1", "O3"]  # C items need no answer


def step(start: int, duration: int, cost: float, status: str = "ok") -> StepRecord:
    return StepRecord.model_validate(
        {
            "agent": "bid_manager",
            "label": "Bid Manager",
            "tier": "sonnet",
            "model": "m",
            "stage": 4,
            "start_ms": start,
            "duration_ms": duration,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": cost,
            "attempts": 1,
            "status": status,
        }
    )


def test_the_retry_is_one_card_with_both_calls_counted() -> None:
    merged = merge_steps(step(0, 100, 0.01), step(150, 50, 0.02))
    assert (merged.start_ms, merged.duration_ms) == (0, 200)
    assert (merged.tokens_in, merged.tokens_out, merged.attempts) == (20, 10, 2)
    assert merged.cost_usd == pytest.approx(0.03)
    assert merged.status == "retried" and "retried" in merged.flags
    summary = describe(merged, [], 1, ["O4", "O5"]).summary
    assert summary.endswith("Not answered by the Bid Manager: O4, O5.")


def test_the_report_lists_what_was_never_answered_and_is_still_open() -> None:
    bid_round = BidRound(no=1, draft_no=2, changes=[], answered=[], not_answered=["O2", "O3"])
    state = RunState.model_validate(
        {
            "run_id": "r",
            "mode": "full",
            "brief": "b",
            "revisions": [bid_round.model_dump()],
            "tracker": [item("O2").model_dump(), item("O3", status="fixed").model_dump()],
        }
    )
    rows = not_answered(state)
    assert [(r.objection_id, r.round, r.text) for r in rows] == [("O2", 1, "O2 text")]
    assert rows[0].action == "Not answered by the Bid Manager"


# --- Fix 3: a gate item reads as the seat's own reason ---


def test_the_memo_shows_the_gate_seat_reason() -> None:
    seat = SeatResult(
        seat_id="security",
        kind="gate",
        title="Security Officer",
        status="answered",
        able=False,
        items=[
            ChecklistResult(
                id="access_control",
                label="Access control",
                must=True,
                status="not_met",
                reason="no single sign-on for claims staff",
            ),
            ChecklistResult(id="data_protection", label="Data protection", must=True, status="met"),
        ],
    )
    assert seat_reason(seat, []) == "Access control: no single sign-on for claims staff."


# --- Fix 4: client-only items and assumptions appear once ---


def draft(seat: str, text: str, claim_ids: tuple[str, ...] = ()) -> ItemDraft:
    return ItemDraft(
        seat=seat, kind="C", severity="condition", text=text, claim_ids=claim_ids, resolve_hint="h"
    )


def test_a_client_item_raised_again_by_its_seat_keeps_its_id() -> None:
    tracker = add_items([], [draft("cfo", "Confirm the retention rule.", ("C4",))], 1)
    again = add_items(tracker, [draft("cfo", "Confirm the data-retention rule.", ("C4",))], 2)
    assert [(t.id, t.text) for t in again] == [("C1", "Confirm the data-retention rule.")]


def test_near_identical_client_items_from_two_seats_merge() -> None:
    tracker = add_items([], [draft("cfo", "Confirm the retention rule.")], 1)
    merged = add_items(tracker, [draft("security", "confirm the retention rule!")], 1)
    assert [(t.id, t.seat) for t in merged] == [("C1", "cfo")]
    other = add_items(merged, [draft("security", "Confirm the peak volume.")], 1)
    assert [t.id for t in other] == ["C1", "C2"]


def test_fixable_items_are_never_merged() -> None:
    fixable = ItemDraft(seat="cfo", kind="O", severity="blocker", text="Same text.")
    assert [t.id for t in add_items([], [fixable, fixable], 1)] == ["O1", "O2"]


def test_the_confirm_list_shows_each_condition_once() -> None:
    tracker = [
        item("C1", text="Confirm the retention rule."),
        item("C2", seat="security", text="Confirm the retention rule"),
        item("C3", text="Confirm the peak."),
    ]
    assert open_conditions(tracker) == ["Confirm the retention rule.", "Confirm the peak."]


def test_an_assumption_already_in_the_proposal_is_not_added_again() -> None:
    first = DraftClaim(
        section="assumptions", text=ASSUMPTION_PREFIX + "the retention rule.", origin="assumption"
    )
    second = DraftClaim(
        section="assumptions",
        text="Confirm with the client: The retention rule",
        origin="assumption",
    )
    claims = assemble_claims([first, second], None)
    texts = [normalize_text(c.text) for c in claims if c.origin == "assumption"]
    assert texts.count("the retention rule") == 1
    again = apply_change(
        claims, change("assume", None, "Confirm with the client: the retention rule.")
    )
    assert again.refused == "duplicate"


# --- Fix 5: the holiday wording ---


def test_the_holiday_assumption_says_weekdays_and_public_holidays() -> None:
    assert (
        HOLIDAYS_NOT_CHECKED
        == "the dates count weekdays only; public holidays are not checked yet."
    )


# --- Fix 6: an added statement goes to the section named, else the objection's claim's ---


def test_an_added_statement_goes_to_the_named_section() -> None:
    named = apply_change(CLAIMS, change("add", "C2", "A kill switch.", section="risks"))
    assert named.claims[-1].section == "risks"
    unknown = Change.model_validate(
        {"objection_id": "O1", "action": "add", "text": "A kill switch.", "section": "nowhere"}
    )
    assert apply_change(CLAIMS, unknown, "scope").claims[-1].section == "scope"
    assert apply_change(CLAIMS, unknown).claims[-1].section == "proposed_solution"


def test_without_a_section_the_objections_claim_decides() -> None:
    tracker = [item("O1", claim_ids=["C4"])]
    claims, applied, _ = apply_bid_changes(
        CLAIMS, tracker, [change("add", None, "The feed has a fallback file.")], 1
    )
    assert applied[0].outcome == "applied" and claims[-1].section == "risks"
