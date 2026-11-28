"""Phase 4 follow-up rules: the Bid Manager cannot change commercial facts, cannot skip an open
objection unnoticed, and client-only items and assumptions appear once."""

import pytest

from agents.bid_manager import (
    REFUSALS,
    describe,
    merge_steps,
    missing_ids,
    order_open,
    refusal_notes,
)
from domain.claims import (
    HOLIDAYS_NOT_CHECKED,
    apply_change,
    assemble_claims,
    honest_commercial_model,
    normalize_text,
    states_commercial_fact,
)
from domain.report import decisions, not_answered, open_conditions, seat_reason
from domain.revision import apply_bid_changes
from domain.tracker import ItemDraft, add_items, flag_decisions
from schemas.answers import Change
from schemas.board import ChecklistResult, SeatResult
from schemas.claims import ASSUMPTION_PREFIX, Claim, DraftClaim
from schemas.revision import AppliedChange, BidRound
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
    answered = [applied("O2", "applied"), applied("O4", "protected")]
    # A refused change answers nothing; C items need no answer.
    assert missing_ids(open_items, answered) == ["O4", "O1", "O3"]


def applied(objection_id: str, outcome: str) -> AppliedChange:
    return AppliedChange.model_validate(
        {"objection_id": objection_id, "action": "add", "outcome": outcome}
    )


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


# --- Follow-up 2 ---

OWN_TERMS = [
    "Scope changes are handled through a written change request that states the effect on "
    "engineer-days and cost, and is agreed before work starts.",
    "Personal data is encrypted in transit and at rest, and access to a claim requires the "
    "claim number plus a secure link.",
    "The data feed may be late, so the page shows when it was last updated.",
    "Acceptance: the client signs off each phase before the next one starts.",
]


@pytest.mark.parametrize("text", OWN_TERMS)
def test_our_own_terms_are_not_commercial_facts(text: str) -> None:
    assert not states_commercial_fact(text)
    assert apply_change(CLAIMS, change("add", None, text)).refused is None


@pytest.mark.parametrize(
    "text",
    [
        "A not-to-exceed ceiling.",
        "Two more engineers.",
        "Ten working days.",
        "Starts 7 Dec.",
        "Go-live on December 18.",
        "A day rate of 550.",
        "A 10% discount.",
    ],
)
def test_new_figures_and_terms_are_still_commercial_facts(text: str) -> None:
    assert states_commercial_fact(text)


def answer(objection_id: str, action: str, claim_id: str | None, text: str) -> Change:
    return change(action, claim_id, text).model_copy(update={"objection_id": objection_id})


def test_an_add_ignores_the_claim_id_and_keeps_the_refused_text() -> None:
    tracker = [item("O2", seat="procurement")]
    sent = answer("O2", "add", "C5", "A fixed price of $24,000.")
    claims, applied_now, marked = apply_bid_changes(CLAIMS, tracker, [sent], 1)
    assert claims == CLAIMS and applied_now[0].outcome == "protected"
    assert applied_now[0].old_text is None
    assert applied_now[0].proposed_text == "A fixed price of $24,000."
    assert marked[0].answered_in == []  # refused: not answered
    fine = answer("O2", "add", "C5", "Changes go through a written change request.")
    added, done, marked = apply_bid_changes(CLAIMS, tracker, [fine], 1)
    assert done[0].outcome == "applied" and done[0].claim_id == "C6"
    assert added[-1].section == "proposed_solution"  # not C5's locked cost section
    assert marked[0].answered_in == [1]


def test_the_retry_says_why_each_change_was_refused_and_how_to_fix_it() -> None:
    changes = [
        AppliedChange.model_validate(
            {
                "objection_id": "O2",
                "action": "add",
                "claim_id": "C7",
                "proposed_text": "Fixed price.",
                "outcome": "protected",
            }
        ),
        AppliedChange.model_validate({"objection_id": "O3", "action": "add", "outcome": "empty"}),
        applied("O1", "applied"),
    ]
    notes = refusal_notes(changes, ["O2", "O3"])
    assert [(n["objection_id"], n["claim_id"], n["text"]) for n in notes] == [
        ("O2", None, "Fixed price."),
        ("O3", None, ""),
    ]
    assert notes[0]["why_refused"] == REFUSALS["protected"]
    assert "commitment" in str(notes[0]["how_to_fix"])
    assert "text" in str(notes[1]["how_to_fix"])


@pytest.mark.parametrize(
    ("section", "text", "origin"),
    [
        ("assumptions", "The client runs a test environment.", "assumption"),
        ("scope", "Confirm with the client: who joins the pilot.", "assumption"),
        ("scope", "The page shows claim status only.", "proposal"),
    ],
)
def test_assumptions_always_carry_the_to_confirm_tag(section: str, text: str, origin: str) -> None:
    drafted = assemble_claims([DraftClaim(section=section, text=text, origin="proposal")], None)
    assert drafted[0].origin == origin
    added = apply_change(CLAIMS, change("add", None, text, section=section)).claims[-1]
    assert added.origin == origin
    if section != "assumptions":  # a replace keeps the claim's own section
        assert apply_change(CLAIMS, change("replace", "C2", text)).claims[1].origin == origin


def o_draft(
    text: str, seat: str = "cfo", claim: str = "C8", severity: str = "condition"
) -> ItemDraft:
    return ItemDraft(seat=seat, kind="O", severity=severity, text=text, claim_ids=(claim,))


def test_a_repeated_objection_on_the_same_claim_keeps_its_id() -> None:
    first = add_items([], [o_draft("The time and materials model leaves our budget exposed.")], 1)
    again = add_items(
        first,
        [o_draft("Time and materials still leaves the budget exposed.", severity="blocker")],
        2,
    )
    assert [(t.id, t.severity, t.raised_round) for t in again] == [("O1", "blocker", 1)]
    assert again[0].text.startswith("Time and materials still")
    other_claim = add_items(first, [o_draft("The budget stays exposed.", claim="C9")], 2)
    other_seat = add_items(first, [o_draft("The budget stays exposed.", seat="vp_director")], 2)
    other_point = add_items(first, [o_draft("The rollout has no rollback plan at all.")], 2)
    assert [len(x) for x in (other_claim, other_seat, other_point)] == [2, 2, 2]


def test_a_gate_line_raised_again_keeps_its_id() -> None:
    def line(text: str) -> ItemDraft:
        return ItemDraft(
            seat="procurement",
            kind="O",
            severity="blocker",
            text=text,
            item_id="change_control",
            must=True,
        )

    tracker = add_items([], [line("Change control: no change process.")], 1)
    again = add_items(tracker, [line("Change control: still no change process.")], 2)
    assert [(t.id, t.must, t.text) for t in again] == [
        ("O1", True, "Change control: still no change process.")
    ]


CAP_CLAIM = "The commercial model is time and materials with a cap."


@pytest.mark.parametrize(
    ("brief", "contract", "expected", "origin"),
    [
        (
            "Billed time-and-materials at $600 per engineer-day.",
            "tm",
            "The commercial model is time and materials.",
            "derived",
        ),
        ("A fixed-price change.", "fixed", "The commercial model is fixed price.", "derived"),
        (
            "No contract details.",
            None,
            ASSUMPTION_PREFIX + "the commercial model (fixed price or time and materials).",
            "assumption",
        ),
        ("Time and materials with a cap of $30,000.", "tm", CAP_CLAIM, "proposal"),
    ],
)
def test_an_invented_cap_becomes_the_plain_contract_type(
    brief: str, contract: str | None, expected: str, origin: str
) -> None:
    claims = [
        Claim(id="C1", section="team_cost", text=CAP_CLAIM, origin="proposal"),
        Claim(id="C2", section="scope", text="The page shows claim status.", origin="proposal"),
    ]
    honest = honest_commercial_model(claims, contract, brief)
    assert (honest[0].text, honest[0].origin) == (expected, origin)
    assert honest[1] == claims[1]


@pytest.mark.parametrize(
    ("text", "contract", "decision"),
    [
        ("We need a firm fixed price before we sign.", "tm", True),
        ("Add a not-to-exceed cap on the total.", "tm", True),
        ("The fixed price has no breakdown by phase.", "fixed", False),
        ("Change control is missing.", "tm", False),
        ("Lower the day rate for phase 2.", "fixed", True),
    ],
)
def test_terms_changes_are_decisions_for_lumen_works(
    text: str, contract: str, decision: bool
) -> None:
    flagged = flag_decisions([item("O1", text=text)], contract)
    assert flagged[0].decision is decision
    assert decisions(flagged) == ([text] if decision else [])
    assert missing_ids(flagged, []) == ([] if decision else ["O1"])
