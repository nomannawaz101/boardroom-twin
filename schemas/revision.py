"""The revision loop (plan sections 4.5 to 4.7): Bid Manager rounds, the stop decision and the
final report. All built by code from model answers; no model computes any of it."""

from typing import Literal

from pydantic import BaseModel

StopReason = Literal["all_proceed", "no_gain", "max_rounds", "guard"]
ChangeOutcome = Literal[
    "applied",
    "locked",
    "unknown_claim",
    "unknown_objection",
    "empty",
    "client_only",
    "protected",
    "duplicate",
]


class AppliedChange(BaseModel):
    """One Bid Manager change and what code did with it. Only `applied` changed the proposal."""

    objection_id: str
    action: Literal["replace", "remove", "add", "assume"]
    claim_id: str | None = None  # the claim changed, or the new claim's id
    old_text: str | None = None
    new_text: str | None = None
    outcome: ChangeOutcome


class BidRound(BaseModel):
    no: int
    draft_no: int  # the draft this round produced
    changes: list[AppliedChange]
    answered: list[str]  # objection ids the Bid Manager answered (not "fixed": seats decide that)
    # Open fixable objections the Bid Manager left out, even after one retry naming them.
    not_answered: list[str] = []


class StopDecision(BaseModel):
    stopped: bool
    reasons: list[StopReason]
    lines: list[str]  # the reasons in words, written by code


class KeyNumber(BaseModel):
    label: str
    value: str
    note: str = ""


class MemoRow(BaseModel):
    seat_id: str
    title: str
    decision: str
    vote: str | None = None
    outcome: str | None = None
    score: float | None = None
    needed: float | None = None
    reason: str = ""


class ReportChange(BaseModel):
    objection_id: str
    round: int
    action: str
    text: str


class Report(BaseModel):
    verdict_code: str
    verdict: str
    headline: str
    summary: str
    numbers: list[KeyNumber]
    changes: list[ReportChange]
    memo: list[MemoRow]
    confirm_with_client: list[str]
    stop: StopDecision
    not_answered: list[ReportChange] = []  # still open, never answered by the Bid Manager
