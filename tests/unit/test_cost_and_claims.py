import pytest

from domain.claims import (
    ASSUMPTION_PREFIX,
    apply_change,
    assemble_claims,
    format_money,
    next_claim_id,
    rebuild_calculated,
)
from domain.cost import CostInputError, PhaseDays, estimate_cost, price_phases
from schemas.answers import Change
from schemas.claims import Claim, DraftClaim
from schemas.cost import PhaseEffort


def northwind_estimate():  # noqa: ANN201 - test helper
    phases = [PhaseEffort(no=1, engineers=2, weeks=2), PhaseEffort(no=2, engineers=2, weeks=2)]
    return estimate_cost(phases, 600, "USD")


# --- Cost maths ---


def test_northwind_cost_matches_a_hand_calculation() -> None:
    estimate = northwind_estimate()
    assert [(p.days, p.cost) for p in estimate.phases] == [(10, 12000.0), (10, 12000.0)]
    assert (estimate.engineer_days, estimate.total) == (40, 24000.0)


def test_summit_ridge_change_request_is_33000() -> None:
    estimate = estimate_cost([PhaseEffort(no=1, engineers=2, weeks=6)], 550, "USD")
    assert (estimate.engineer_days, estimate.total) == (60, 33000.0)


def test_money_rounds_half_up_to_cents() -> None:
    estimate = price_phases([PhaseDays(1, 1, 1)], 0.125, "USD")
    assert estimate.total == 0.13


def test_fractional_days_are_priced() -> None:
    assert price_phases([PhaseDays(1, 3, 2.5)], 400, "USD").total == 3000.0


@pytest.mark.parametrize(
    ("engineers", "days", "rate"), [(0, 5, 600), (2, 0, 600), (2, 5, 0), (-1, 5, 600)]
)
def test_cost_refuses_zero_or_negative_input(engineers: int, days: float, rate: float) -> None:
    with pytest.raises(CostInputError):
        price_phases([PhaseDays(1, engineers, days)], rate, "USD")


def test_cost_needs_a_phase() -> None:
    with pytest.raises(CostInputError):
        price_phases([], 600, "USD")


@pytest.mark.parametrize(
    ("amount", "currency", "text"),
    [(12000, "USD", "$12,000"), (1234.5, "EUR", "€1,234.50"), (500, "CHF", "500 CHF")],
)
def test_format_money(amount: float, currency: str, text: str) -> None:
    assert format_money(amount, currency) == text


# --- Claims and locking ---


def drafts() -> list[DraftClaim]:
    return [
        DraftClaim(
            section="executive_summary", text="A status page for claims.", origin="proposal"
        ),
        DraftClaim(section="team_cost", text="Costs $1 only.", origin="calculated"),
    ]


def test_assemble_numbers_claims_and_appends_locked_calculated_claims() -> None:
    claims = assemble_claims(drafts(), northwind_estimate())
    assert [c.id for c in claims] == ["C1", "C2", "C3", "C4", "C5"]
    calculated = [c for c in claims if c.origin == "calculated"]
    assert [c.text for c in calculated] == [
        "Phase 1: 2 engineers x 10 days x $600 = $12,000.",
        "Phase 2: 2 engineers x 10 days x $600 = $12,000.",
        "Total: 40 engineer-days, $24,000.",
    ]
    assert all(c.locked for c in calculated)


def test_a_model_cannot_mark_its_own_claim_as_calculated() -> None:
    claims = assemble_claims(drafts(), None)
    assert claims[1].origin == "derived" and not claims[1].locked


def test_unknown_origin_from_a_model_becomes_derived() -> None:
    draft = DraftClaim.model_validate({"section": "scope", "text": "x", "origin": "made_up"})
    assert draft.origin == "derived"


@pytest.mark.parametrize("action", ["replace", "remove"])
def test_locked_claims_cannot_be_changed(action: str) -> None:
    claims = assemble_claims(drafts(), northwind_estimate())
    change = Change(objection_id="O1", action=action, claim_id="C5", text="Total: $1.")  # type: ignore[arg-type]
    outcome = apply_change(claims, change)
    assert outcome.refused == "locked"
    assert outcome.claims == claims


def test_unknown_claim_id_is_refused() -> None:
    claims = assemble_claims(drafts(), None)
    change = Change(objection_id="O1", action="replace", claim_id="C99", text="x")
    assert apply_change(claims, change).refused == "unknown_claim"


def test_replace_and_remove_an_unlocked_claim() -> None:
    claims = assemble_claims(drafts(), None)
    replaced = apply_change(
        claims, Change(objection_id="O1", action="replace", claim_id="C1", text="New.")
    )
    assert replaced.refused is None
    assert (replaced.claims[0].text, replaced.claims[0].origin) == ("New.", "proposal")
    removed = apply_change(claims, Change(objection_id="O1", action="remove", claim_id="C1"))
    assert [c.id for c in removed.claims] == ["C2"]


def test_add_and_assume_get_new_ids() -> None:
    claims = assemble_claims(drafts(), None)
    added = apply_change(
        claims, Change(objection_id="O2", action="add", claim_id="C1", text="More.")
    )
    new = added.claims[-1]
    assert (new.id, new.section, new.origin) == ("C3", "executive_summary", "proposal")
    assumed = apply_change(
        claims, Change(objection_id="O3", action="assume", text="Phase 2 funding.")
    )
    new = assumed.claims[-1]
    assert (new.section, new.origin) == ("assumptions", "assumption")
    assert new.text == ASSUMPTION_PREFIX + "Phase 2 funding."


def test_rebuild_restores_calculated_claims_from_the_numbers() -> None:
    claims = assemble_claims(drafts(), northwind_estimate())
    tampered = [c.model_copy(update={"text": "Total: $1."}) if c.id == "C5" else c for c in claims]
    rebuilt = rebuild_calculated(tampered, northwind_estimate())
    assert rebuilt == claims


def test_rebuild_follows_a_changed_estimate() -> None:
    claims = assemble_claims(drafts(), northwind_estimate())
    smaller = estimate_cost([PhaseEffort(no=1, engineers=1, weeks=1)], 600, "USD")
    rebuilt = rebuild_calculated(claims, smaller)
    calculated = [c for c in rebuilt if c.origin == "calculated"]
    assert [c.id for c in calculated] == ["C3", "C4"]
    assert calculated[-1].text == "Total: 5 engineer-days, $3,000."


def test_next_claim_id_ignores_odd_ids() -> None:
    claims = [Claim(id="C2", section="scope", text="x"), Claim(id="X", section="scope", text="y")]
    assert next_claim_id(claims) == "C3"
