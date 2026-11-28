"""Bid Manager changes and the tracker's "fixed means re-read" rule (sections 4.5 and 4.6)."""

from domain.revision import apply_bid_changes
from domain.tracker import apply_reread, gate_drafts, mark_answered, reread_states
from schemas.answers import Change, PreviousState
from schemas.board import ChecklistResult
from schemas.claims import ASSUMPTION_PREFIX, Claim
from schemas.state import TrackerItem

CLAIMS = [
    Claim(id="C1", section="executive_summary", text="One payment.", origin="proposal"),
    Claim(id="C2", section="team_cost", text="Total: $24,000.", origin="calculated", locked=True),
]


def item(item_id: str, seat: str, kind: str = "O", line: str | None = None) -> TrackerItem:
    return TrackerItem.model_validate(
        {
            "id": item_id,
            "seat": seat,
            "kind": kind,
            "text": f"{item_id} text",
            "raised_round": 1,
            "item_id": line,
        }
    )


TRACKER = [item("O1", "cfo"), item("O2", "vp_director"), item("C1", "cfo", "C")]


def change(objection_id: str, action: str, claim_id: str | None = None, text: str = "") -> Change:
    return Change.model_validate(
        {"objection_id": objection_id, "action": action, "claim_id": claim_id, "text": text}
    )


# --- Applying the Bid Manager's changes ---


def test_a_replace_is_applied_and_shown_as_answered_not_fixed() -> None:
    claims, applied, tracker = apply_bid_changes(
        CLAIMS, TRACKER, [change("O1", "replace", "C1", "Two phases.")], 1
    )
    assert claims[0].text == "Two phases." and claims[0].origin == "proposal"
    assert [(a.outcome, a.old_text, a.new_text) for a in applied] == [
        ("applied", "One payment.", "Two phases.")
    ]
    o1 = tracker[0]
    assert (o1.status, o1.answered_in) == ("open", [1])


def test_a_calculated_claim_can_never_be_changed() -> None:
    for action in ("replace", "remove"):
        claims, applied, tracker = apply_bid_changes(
            CLAIMS, TRACKER, [change("O1", action, "C2", "Total: $1.")], 1
        )
        assert claims == CLAIMS
        assert applied[0].outcome == "locked"
        assert tracker[0].answered_in == []


def test_a_change_must_name_an_open_objection() -> None:
    fixed = [TRACKER[0].model_copy(update={"status": "fixed"}), *TRACKER[1:]]
    changes = [change("X9", "replace", "C1", "x"), change("O1", "replace", "C1", "y")]
    claims, applied, _ = apply_bid_changes(CLAIMS, fixed, changes, 1)
    assert [a.outcome for a in applied] == ["unknown_objection", "unknown_objection"]
    assert claims == CLAIMS


def test_unknown_claims_and_empty_text_are_refused() -> None:
    changes = [change("O1", "replace", "C99", "x"), change("O2", "add", "C1", "  ")]
    _, applied, _ = apply_bid_changes(CLAIMS, TRACKER, changes, 1)
    assert [a.outcome for a in applied] == ["unknown_claim", "empty"]


def test_an_assumption_is_added_and_the_item_stays_open() -> None:
    claims, applied, tracker = apply_bid_changes(
        CLAIMS, TRACKER, [change("C1", "assume", None, "Phase 2 funding is approved.")], 2
    )
    new = claims[-1]
    assert (new.id, new.section, new.origin) == ("C3", "assumptions", "assumption")
    assert new.text == ASSUMPTION_PREFIX + "Phase 2 funding is approved."
    assert applied[0].claim_id == "C3"
    c1 = next(t for t in tracker if t.id == "C1")
    assert (c1.status, c1.answered_in) == ("open", [2])


def test_the_word_limit_is_checked_on_model_replies_without_the_prefix() -> None:
    from schemas.common import FROM_MODEL

    ok = ASSUMPTION_PREFIX + " ".join(["word"] * 20)
    Change.model_validate(
        {"objection_id": "O1", "action": "assume", "text": ok}, context={FROM_MODEL: True}
    )
    too_long = {"objection_id": "O1", "action": "add", "text": " ".join(["word"] * 21)}
    try:
        Change.model_validate(too_long, context={FROM_MODEL: True})
    except ValueError as error:
        assert "at most 20 words" in str(error)
    else:
        raise AssertionError("a 21-word change must fail its check")


# --- Fixed only when the raising seat re-reads and agrees ---


def test_only_the_raising_seat_can_fix_its_item() -> None:
    previous = [
        PreviousState(id="O1", state="resolved"),
        PreviousState(id="O2", state="resolved"),
        PreviousState(id="O99", state="resolved"),
    ]
    states = reread_states(TRACKER, "cfo", previous)
    assert states == {"O1": "resolved"}  # O2 belongs to the VP; O99 is unknown
    tracker = apply_reread(TRACKER, states, 2)
    assert [(t.id, t.status) for t in tracker] == [("O1", "fixed"), ("O2", "open"), ("C1", "open")]
    assert tracker[0].history[0].round == 2 and tracker[0].history[0].state == "resolved"


def test_partly_and_open_keep_the_item_open() -> None:
    previous = [PreviousState(id="O1", state="partly"), PreviousState(id="C1", state="open")]
    tracker = apply_reread(TRACKER, reread_states(TRACKER, "cfo", previous), 2)
    assert [(t.id, t.status, len(t.history)) for t in tracker] == [
        ("O1", "open", 1),
        ("O2", "open", 0),
        ("C1", "open", 1),
    ]


def test_an_item_the_seat_says_nothing_about_stays_open_without_history() -> None:
    tracker = apply_reread(TRACKER, reread_states(TRACKER, "cfo", []), 2)
    assert tracker == TRACKER


def test_a_gates_checklist_answer_counts_as_its_reread_of_that_line() -> None:
    gate_items = [
        item("O5", "procurement", line="change_control"),
        item("O6", "procurement", line="acceptance_payment"),
    ]
    lines = [
        ChecklistResult(id="change_control", label="Change control", must=True, status="met"),
        ChecklistResult(id="acceptance_payment", label="Acceptance", must=False, status="partly"),
    ]
    states = reread_states(gate_items, "procurement", [], lines)
    assert states == {"O5": "resolved", "O6": "partly"}
    # The gate's own previous list wins over its checklist answer.
    states = reread_states(gate_items, "procurement", [PreviousState(id="O5", state="open")], lines)
    assert states["O5"] == "open"


def test_a_line_already_open_gets_no_second_item() -> None:
    open_line = [item("O6", "procurement", line="acceptance_payment")]
    lines = [
        ChecklistResult(id="acceptance_payment", label="Acceptance", must=False, status="partly")
    ]
    assert gate_drafts("procurement", lines, [], open_line) == []
    assert len(gate_drafts("procurement", lines, [], [])) == 1


def test_mark_answered_records_the_round() -> None:
    marked = mark_answered(TRACKER, {"O2"}, 1)
    assert [t.answered_in for t in marked] == [[], [1], []]


def test_a_client_only_item_can_only_be_answered_with_an_assumption() -> None:
    changes = [
        change("C1", "replace", "C1", "We already have funding."),
        change("C1", "assume", None, "Phase 2 funding."),
    ]
    claims, applied, tracker = apply_bid_changes(CLAIMS, TRACKER, changes, 1)
    assert [a.outcome for a in applied] == ["client_only", "applied"]
    assert claims[0].text == "One payment."
    assert next(t for t in tracker if t.id == "C1").status == "open"
