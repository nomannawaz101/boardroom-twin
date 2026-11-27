"""Board seats: one module for all five, because seats are data (plan section 11.1).

A scoring seat rates its criteria; a gate seat answers its checklist. Neither returns a total,
a vote or an outcome: code computes those (domain/scoring.py, domain/gates.py).
"""

from dataclasses import dataclass, field
from typing import Any

from agents.common import inputs_block, plural, system_prompt
from agents.registry import received_line
from config import SEAT_MAX_OBJECTIONS
from domain.claims import ORIGIN_TAGS
from domain.seats import SEATS_BY_ID, SeatKind, SeatSpec
from llm.client import AgentResult, Runtime, run_agent
from schemas.answers import GateSeatAnswer, ScoringSeatAnswer
from schemas.board import PlannedSeat, SeatResult
from schemas.case_file import CaseFile
from schemas.claims import Claim
from schemas.common import REQUIRED_ITEMS, match_key
from schemas.revision import AppliedChange
from schemas.state import TrackerItem
from schemas.step import StepRecord

SeatAnswer = ScoringSeatAnswer | GateSeatAnswer
PROMPTS: dict[SeatKind, str] = {"scoring": "scoring_seat", "gate": "gate_seat"}
SCHEMAS: dict[SeatKind, type[ScoringSeatAnswer] | type[GateSeatAnswer]] = {
    "scoring": ScoringSeatAnswer,
    "gate": GateSeatAnswer,
}


def seat_terms(spec: SeatSpec) -> dict[str, Any]:
    if spec.kind == "scoring":
        return {
            "criteria": [{"id": c.id, "label": c.label, "weight": c.weight} for c in spec.criteria]
        }
    return {"checklist": [{"id": i.id, "label": i.label, "must": i.must} for i in spec.checklist]}


def proposal_lines(claims: list[Claim]) -> list[dict[str, str]]:
    return [
        {"id": c.id, "section": c.section, "tag": ORIGIN_TAGS.get(c.origin, ""), "text": c.text}
        for c in claims
    ]


FIRST_ROUND_RULE = "an empty list (this is the first round)."
REVOTE_RULE = (
    'for every item in "your_open_items", re-read the new proposal and give its id with '
    '"resolved", "partly" or "open". Only "resolved" closes it, so say resolved only if the new '
    "text really answers it. Raise new objections only for problems not already in that list."
)


@dataclass(frozen=True)
class Review:
    """What a seat reviews: the draft, and in a re-vote its own open items and the changes."""

    claims: list[Claim]
    case_file: CaseFile
    draft_no: int
    open_items: list[TrackerItem] = field(default_factory=list)
    changes: list[AppliedChange] = field(default_factory=list)

    @property
    def revote(self) -> bool:
        return self.draft_no > 1


def seat_inputs(seat: PlannedSeat, review: Review) -> str:
    """The seat title (built from the brief) and the client name travel as data, never in the
    system prompt."""
    payload: dict[str, Any] = {
        "your_seat": seat.title,
        "client": review.case_file.client,
        "draft": review.draft_no,
        **seat_terms(SEATS_BY_ID[seat.id]),
        "client_context": {
            "goals": review.case_file.goals,
            "warnings": [w.text for w in review.case_file.warnings],
        },
        "proposal": proposal_lines(review.claims),
    }
    if review.revote:
        payload["your_open_items"] = [
            {"id": t.id, "text": t.text, "claim_ids": t.claim_ids} for t in review.open_items
        ]
        payload["changes_since_last_draft"] = [
            {
                "objection_id": c.objection_id,
                "action": c.action,
                "old": c.old_text,
                "new": c.new_text,
            }
            for c in review.changes
            if c.outcome == "applied"
        ]
    return inputs_block(payload)


async def run(
    seat: PlannedSeat, review: Review, runtime: Runtime
) -> AgentResult[ScoringSeatAnswer] | AgentResult[GateSeatAnswer]:
    """No safe default: a seat that cannot answer is Not reviewed, never given made-up votes."""
    spec = SEATS_BY_ID[seat.id]
    system = system_prompt(
        PROMPTS[spec.kind],
        lens=spec.lens,
        max_objections=SEAT_MAX_OBJECTIONS,
        previous_rule=REVOTE_RULE if review.revote else FIRST_ROUND_RULE,
    )
    user = seat_inputs(seat, review)
    return await run_agent(
        seat.id, system, user, SCHEMAS[spec.kind], runtime=runtime, check=reply_check(spec)
    )


def reply_check(spec: SeatSpec) -> dict[str, object] | None:
    """A gate seat must answer every checklist item; a reply that leaves one out is retried."""
    if spec.kind != "gate":
        return None
    return {REQUIRED_ITEMS: [[item.id, match_key(item.label)] for item in spec.checklist]}


def answered_items(result: SeatResult) -> int:
    return sum(item.status != "missing" for item in result.items)


def summary(result: SeatResult, attempts: int) -> str:
    tries = plural(attempts, "try", "tries")
    if result.status == "not_reviewed" and result.partial:
        return (
            f"Answered only {answered_items(result)} of {len(result.items)} checklist items, "
            f"even after {tries}, so this seat is Not reviewed (partial answer). "
            "The other seats still count."
        )
    if result.status == "not_reviewed":
        return (
            f"Did not answer after {tries}, so this seat is Not reviewed. "
            "The other seats still count."
        )
    if result.kind == "scoring":
        partial = " A criterion was not rated, so code counted it as 0."
        text = (
            f"Rated {plural(len(result.criteria), 'criterion', 'criteria')}. Code scored "
            f"{result.score:.2f} against the {result.needed:.1f} needed: {result.decision}."
        )
    else:
        partial = (
            " Partial answer: an item was still missing after the retries; a must-have that it "
            "answered Not met blocks anyway."
        )
        text = (
            f"Answered {answered_items(result)} of {plural(len(result.items), 'checklist item')}. "
            f"Code decided: {result.decision}."
        )
    return text + (partial if result.partial else "")


def describe(step: StepRecord, result: SeatResult, draft_no: int, claims: int) -> StepRecord:
    """Summary and handoff written by code. A Not reviewed seat says so on its step record."""
    update: dict[str, Any] = {
        "summary": summary(result, step.attempts),
        "handoff_in": received_line(step.agent, f"draft {draft_no}, {plural(claims, 'claim')}."),
    }
    flags = list(step.flags)
    if result.partial and result.kind == "gate":
        flags.append("partial")
    if result.status == "not_reviewed":
        update["status"] = "not_reviewed"
        flags.append("not_reviewed")
    elif step.status == "skipped":
        # The reply failed its check, but code used what it knew for sure (a known Not met).
        update["status"] = "retried"
        flags = [f for f in flags if f != "skipped"]
    update["flags"] = flags
    return step.model_copy(update=update)
