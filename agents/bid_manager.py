"""Bid Manager (Sonnet): answers each open objection by its id, changing only what was objected to.

Code applies the changes (domain/revision.py): locked claims cannot change, unknown ids are
ignored, and an objection is fixed only when its seat re-reads the new text and agrees.
"""

from agents.board_seat import proposal_lines
from agents.common import inputs_block, plural, system_prompt
from agents.registry import passed_line, received_line
from config import CLAIM_MAX_WORDS
from domain.revision import answered_ids
from llm.client import AgentResult, Runtime, run_agent
from schemas.answers import BidManagerAnswer
from schemas.board import BoardPlan
from schemas.case_file import CaseFile
from schemas.claims import Claim
from schemas.revision import AppliedChange
from schemas.state import TrackerItem
from schemas.step import StepRecord

AGENT_ID = "bid_manager"


def objection_lines(open_items: list[TrackerItem], plan: BoardPlan) -> list[dict[str, object]]:
    titles = {s.id: s.title for s in plan.seats}
    return [
        {
            "id": t.id,
            "raised_by": titles.get(t.seat, t.seat),
            "needs_client": t.kind == "C",
            "severity": t.severity,
            "text": t.text,
            "resolve_hint": t.resolve_hint,
            "claim_ids": t.claim_ids,
        }
        for t in open_items
    ]


async def run(
    open_items: list[TrackerItem],
    claims: list[Claim],
    case_file: CaseFile,
    plan: BoardPlan,
    runtime: Runtime,
) -> AgentResult[BidManagerAnswer]:
    payload = {
        "open_objections": objection_lines(open_items, plan),
        "proposal": [
            line | {"locked": claim.locked}
            for line, claim in zip(proposal_lines(claims), claims, strict=True)
        ],
        "client_context": {
            "goals": case_file.goals,
            "warnings": [w.text for w in case_file.warnings],
        },
    }
    system = system_prompt(AGENT_ID, max_words=CLAIM_MAX_WORDS)
    return await run_agent(
        AGENT_ID, system, inputs_block(payload), BidManagerAnswer, runtime=runtime
    )


def describe(step: StepRecord, changes: list[AppliedChange], bid_round: int) -> StepRecord:
    """Written by code: what was answered, and anything code refused."""
    answered = answered_ids(changes)
    refused = [c for c in changes if c.outcome != "applied"]
    summary = (
        f"Round {bid_round}: answered {', '.join(answered) or 'nothing'} with "
        f"{plural(len(changes) - len(refused), 'change')}."
    )
    if refused:
        summary += f" Code refused {plural(len(refused), 'change')} (locked claim or unknown id)."
    return step.model_copy(
        update={
            "summary": summary,
            "handoff_in": received_line(AGENT_ID, "the open objections, each with its id."),
            "handoff_out": passed_line(
                AGENT_ID, f"draft {bid_round + 1} for the board to re-read."
            ),
        }
    )
