from datetime import date

import pytest

from domain.claims import (
    ASSUMPTION_PREFIX,
    HOLIDAYS_NOT_CHECKED,
    MISSING_COST,
    MISSING_START,
    apply_change,
    assemble_claims,
    code_assumptions,
    format_date,
    next_claim_id,
    rebuild_calculated,
)
from domain.cost import estimate_cost
from domain.timeline import plan_schedule
from schemas.answers import Change
from schemas.claims import Claim, DraftClaim
from schemas.cost import CostEstimate, PhaseEffort
from schemas.timeline import Schedule

NORTHWIND_START = date(2026, 12, 7)


def northwind_estimate() -> CostEstimate:
    phases = [PhaseEffort(no=1, engineers=2, weeks=2), PhaseEffort(no=2, engineers=2, weeks=2)]
    return estimate_cost(phases, 600, "USD")


def northwind_schedule() -> Schedule:
    return plan_schedule(NORTHWIND_START, [(1, 10), (2, 10)])


def drafts() -> list[DraftClaim]:
    return [
        DraftClaim(
            section="executive_summary", text="A status page for claims.", origin="proposal"
        ),
        DraftClaim(section="team_cost", text="Costs $1 only.", origin="calculated"),
    ]


def full_draft() -> list[Claim]:
    """C1-C2 model claims, C3 the holidays assumption, C4-C9 calculated claims."""
    return assemble_claims(drafts(), northwind_estimate(), northwind_schedule())


def test_format_date() -> None:
    assert format_date(NORTHWIND_START) == "Mon Dec 7, 2026"


def test_assemble_adds_code_assumptions_then_locked_calculated_claims() -> None:
    claims = full_draft()
    assert [c.id for c in claims] == [f"C{i}" for i in range(1, 10)]
    assert claims[2].text == ASSUMPTION_PREFIX + HOLIDAYS_NOT_CHECKED
    assert claims[2].origin == "assumption" and not claims[2].locked
    calculated = [c for c in claims if c.origin == "calculated"]
    assert [(c.section, c.text) for c in calculated] == [
        ("team_cost", "Phase 1: 2 engineers x 10 days x $600 = $12,000."),
        ("team_cost", "Phase 2: 2 engineers x 10 days x $600 = $12,000."),
        ("team_cost", "Total: 40 engineer-days, $24,000."),
        ("timeline", "Phase 1: Mon Dec 7, 2026 to Fri Dec 18, 2026 (10 working days)."),
        ("timeline", "Phase 2: Mon Dec 21, 2026 to Fri Jan 1, 2027 (10 working days)."),
        (
            "timeline",
            "Go-live: Mon Jan 4, 2027, 20 working days after the start on Mon Dec 7, 2026.",
        ),
    ]
    assert all(c.locked for c in calculated)


def test_missing_cost_and_start_become_assumptions_not_guesses() -> None:
    assert code_assumptions(None, None) == [MISSING_COST, MISSING_START]
    assert code_assumptions(northwind_estimate(), northwind_schedule()) == [HOLIDAYS_NOT_CHECKED]


def test_a_model_cannot_mark_its_own_claim_as_calculated() -> None:
    claims = assemble_claims(drafts(), None)
    assert claims[1].origin == "derived" and not claims[1].locked


def test_unknown_origin_from_a_model_becomes_derived() -> None:
    draft = DraftClaim.model_validate({"section": "scope", "text": "x", "origin": "made_up"})
    assert draft.origin == "derived"


@pytest.mark.parametrize("claim_id", ["C6", "C9"])
@pytest.mark.parametrize("action", ["replace", "remove"])
def test_locked_claims_cannot_be_changed(action: str, claim_id: str) -> None:
    claims = full_draft()
    change = Change.model_validate(
        {"objection_id": "O1", "action": action, "claim_id": claim_id, "text": "Total: $1."}
    )
    outcome = apply_change(claims, change)
    assert outcome.refused == "locked"
    assert outcome.claims == claims


def test_unknown_claim_id_is_refused() -> None:
    claims = assemble_claims(drafts(), None)
    change = Change(objection_id="O1", action="replace", claim_id="C99", text="x")
    assert apply_change(claims, change).refused == "unknown_claim"


def test_replace_and_remove_an_unlocked_claim() -> None:
    claims = assemble_claims(drafts(), None)  # C1, C2, then C3 and C4 code assumptions
    replaced = apply_change(
        claims, Change(objection_id="O1", action="replace", claim_id="C1", text="New.")
    )
    assert replaced.refused is None
    assert (replaced.claims[0].text, replaced.claims[0].origin) == ("New.", "proposal")
    removed = apply_change(claims, Change(objection_id="O1", action="remove", claim_id="C1"))
    assert [c.id for c in removed.claims] == ["C2", "C3", "C4"]


def test_add_and_assume_get_new_ids() -> None:
    claims = assemble_claims(drafts(), None)
    added = apply_change(
        claims, Change(objection_id="O2", action="add", claim_id="C1", text="More.")
    )
    new = added.claims[-1]
    assert (new.id, new.section, new.origin) == ("C5", "executive_summary", "proposal")
    assumed = apply_change(
        claims, Change(objection_id="O3", action="assume", text="Phase 2 funding.")
    )
    new = assumed.claims[-1]
    assert (new.section, new.origin) == ("assumptions", "assumption")
    assert new.text == ASSUMPTION_PREFIX + "Phase 2 funding."


def test_rebuild_restores_calculated_claims_from_the_numbers() -> None:
    claims = full_draft()
    tampered = [
        c.model_copy(update={"text": "Total: $1."}) if c.id in ("C6", "C9") else c for c in claims
    ]
    assert rebuild_calculated(tampered, northwind_estimate(), northwind_schedule()) == claims


def test_rebuild_follows_a_changed_estimate() -> None:
    claims = assemble_claims(drafts(), northwind_estimate())  # C3 missing start, C4-C6 cost
    smaller = estimate_cost([PhaseEffort(no=1, engineers=1, weeks=1)], 600, "USD")
    calculated = [c for c in rebuild_calculated(claims, smaller) if c.origin == "calculated"]
    assert [c.id for c in calculated] == ["C4", "C5"]
    assert calculated[-1].text == "Total: 5 engineer-days, $3,000."


def test_next_claim_id_ignores_odd_ids() -> None:
    claims = [Claim(id="C2", section="scope", text="x"), Claim(id="X", section="scope", text="y")]
    assert next_claim_id(claims) == "C3"
