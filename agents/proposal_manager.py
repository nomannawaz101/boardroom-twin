"""Proposal Manager (Sonnet): draft 1 as short tagged claims in the 9 standard sections."""

from agents.common import dump, inputs_block, plural, system_prompt, with_text
from agents.registry import passed_line, received_line
from config import CLAIM_MAX_WORDS, PM_TARGET_CLAIMS
from domain.claims import calculated_texts
from llm.client import AgentResult, Runtime, run_agent
from schemas.answers import ProposalManagerAnswer, SolutionArchitectAnswer
from schemas.case_file import CaseFile
from schemas.claims import Claim
from schemas.cost import CostEstimate, PhaseEffort
from schemas.step import StepRecord
from schemas.timeline import Schedule

AGENT_ID = "proposal_manager"


async def run(
    case_file: CaseFile,
    design: SolutionArchitectAnswer,
    estimate: CostEstimate | None,
    schedule: Schedule | None,
    efforts: list[PhaseEffort],
    runtime: Runtime,
) -> AgentResult[ProposalManagerAnswer]:
    payload = {
        "case_file": dump(case_file),
        "design": dump(design),
        "locked_by_code": [text for _, text in calculated_texts(estimate, schedule, efforts)],
    }
    system = system_prompt(
        AGENT_ID,
        min_claims=PM_TARGET_CLAIMS[0],
        max_claims=PM_TARGET_CLAIMS[1],
        max_words=CLAIM_MAX_WORDS,
    )
    return await run_agent(
        AGENT_ID,
        system,
        inputs_block(payload),
        ProposalManagerAnswer,
        runtime=runtime,
        default=ProposalManagerAnswer(),
    )


def describe(step: StepRecord, claims: list[Claim], retagged: int) -> StepRecord:
    sections = len({c.section for c in claims})
    summary = (
        f"Wrote draft 1 as {plural(len(claims), 'short claim')} in "
        f"{plural(sections, 'section')}. Facts carry a tag, recommendations do not, and "
        "calculated claims are locked."
    )
    if retagged:
        summary += f" Code re-tagged {plural(retagged, 'claim')} TO CONFIRM."
    return with_text(
        step,
        summary,
        received_line(AGENT_ID, "the case file, the design and the locked cost and dates."),
        passed_line(AGENT_ID, "draft 1 and the context flags."),
    )
