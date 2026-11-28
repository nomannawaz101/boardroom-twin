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
REFUSALS = {
    "locked": "a calculated claim is locked",
    "unknown_claim": "no such claim",
    "unknown_objection": "no open objection with that id",
    "empty": "no text",
    "client_only": "a client item can only be an assumption",
    "protected": "commercial facts, dates and brief claims can only change through an assumption",
    "duplicate": "the same assumption is already in the proposal",
}


def order_open(open_items: list[TrackerItem]) -> list[TrackerItem]:
    """Blockers first, then conditions; the tracker order within each."""
    return sorted(open_items, key=lambda t: t.severity != "blocker")


# Why code refused a change and how to fix it, for the retry.
FIXES = {
    "locked": "Leave the calculated claim alone; add a new statement instead.",
    "unknown_claim": 'Use a claim id from the proposal, or use "add" for a new statement.',
    "protected": "Do not set contract terms, prices, rates, team size or dates. Write our own "
    'commitment without new figures, or "assume" a fact only the client knows.',
    "empty": 'Write the sentence in "text".',
    "unknown_objection": "Use an open objection id from the inputs.",
    "client_only": 'Answer an objection whose id starts with C only with "assume".',
    "duplicate": "That assumption is already in the proposal; write a commitment instead.",
}


def missing_ids(open_items: list[TrackerItem], changes: list[AppliedChange]) -> list[str]:
    """Open fixable objections without an applied change, blockers first. A refused change
    does not answer anything. Decisions for Lumen Works are not the Bid Manager's to answer."""
    answered = {c.objection_id for c in changes if c.outcome == "applied"}
    return [
        t.id
        for t in order_open(open_items)
        if t.kind == "O" and not t.decision and t.id not in answered
    ]


def refusal_notes(changes: list[AppliedChange], missing: list[str]) -> list[dict[str, object]]:
    """For the retry: each refused change on a missing objection, why, and how to fix it."""
    return [
        {
            "objection_id": c.objection_id,
            "action": c.action,
            "claim_id": c.claim_id if c.action in ("replace", "remove") else None,
            "text": c.proposed_text or "",
            "why_refused": REFUSALS[c.outcome],
            "how_to_fix": FIXES[c.outcome],
        }
        for c in changes
        if c.outcome != "applied" and c.objection_id in missing
    ]


def merge_steps(first: StepRecord, retry: StepRecord) -> StepRecord:
    """One card for the call and its retry: the time, tokens and cost of both."""
    return retry.model_copy(
        update={
            "start_ms": first.start_ms,
            "duration_ms": retry.start_ms + retry.duration_ms - first.start_ms,
            "tokens_in": first.tokens_in + retry.tokens_in,
            "tokens_out": first.tokens_out + retry.tokens_out,
            "cost_usd": first.cost_usd + retry.cost_usd,
            "attempts": first.attempts + retry.attempts,
            "tool_calls": [*first.tool_calls, *retry.tool_calls],
            "flags": sorted({*first.flags, *retry.flags, "retried"}),
            "status": "retried" if retry.status == "ok" else retry.status,
        }
    )


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
            "lumen_works_decision": t.decision,
        }
        for t in open_items
    ]


async def run(
    open_items: list[TrackerItem],
    claims: list[Claim],
    case_file: CaseFile,
    plan: BoardPlan,
    runtime: Runtime,
    missing: list[str] | None = None,
    refused: list[dict[str, object]] | None = None,
) -> AgentResult[BidManagerAnswer]:
    """`missing` names the objections a first answer left unanswered, `refused` the changes
    code refused for them, with why and how to fix: the retry answers those."""
    payload: dict[str, object] = {
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
    if missing:
        payload["answer_these_now"] = missing
    if refused:
        payload["refused_changes"] = refused
    system = system_prompt(AGENT_ID, max_words=CLAIM_MAX_WORDS)
    return await run_agent(
        AGENT_ID, system, inputs_block(payload), BidManagerAnswer, runtime=runtime
    )


def describe(
    step: StepRecord,
    changes: list[AppliedChange],
    bid_round: int,
    not_answered: list[str] | None = None,
) -> StepRecord:
    """Written by code: what was answered, anything code refused, and anything left out."""
    answered = answered_ids(changes)
    refused = [c for c in changes if c.outcome != "applied"]
    summary = (
        f"Round {bid_round}: answered {', '.join(answered) or 'nothing'} with "
        f"{plural(len(changes) - len(refused), 'change')}."
    )
    if refused:
        reasons = ", ".join(sorted({REFUSALS[c.outcome] for c in refused}))
        summary += f" Code refused {plural(len(refused), 'change')}: {reasons}."
    if not_answered:
        summary += f" Not answered by the Bid Manager: {', '.join(not_answered)}."
    return step.model_copy(
        update={
            "summary": summary,
            "handoff_in": received_line(AGENT_ID, "the open objections, each with its id."),
            "handoff_out": passed_line(
                AGENT_ID, f"draft {bid_round + 1} for the board to re-read."
            ),
        }
    )
