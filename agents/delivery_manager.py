"""Delivery Manager (Sonnet): engineers and weeks per phase. Code computes every total."""

from agents.common import dump, inputs_block, plural, system_prompt, with_text
from agents.registry import passed_line, received_line
from domain.claims import format_money, format_number
from llm.client import AgentResult, Runtime, run_agent
from schemas.answers import DeliveryManagerAnswer, SolutionArchitectAnswer
from schemas.case_file import CaseFile
from schemas.cost import CostEstimate, PhaseEffort
from schemas.step import StepRecord
from tools import cost_calculator

AGENT_ID = "delivery_manager"
TOOLS = [cost_calculator.NAME]


async def run(
    case_file: CaseFile, design: SolutionArchitectAnswer, runtime: Runtime
) -> AgentResult[DeliveryManagerAnswer]:
    payload = {
        "team": dump(case_file.team),
        "rate": dump(case_file.rate),
        "start": case_file.start,
        "peak": case_file.peak,
        "warnings": [w.text for w in case_file.warnings],
        "design_phases": [p.model_dump(mode="json") for p in design.phases],
    }
    return await run_agent(
        AGENT_ID,
        system_prompt(AGENT_ID),
        inputs_block(payload),
        DeliveryManagerAnswer,
        TOOLS,
        runtime=runtime,
        default=DeliveryManagerAnswer(),
    )


def describe(
    step: StepRecord, efforts: list[PhaseEffort], estimate: CostEstimate | None
) -> StepRecord:
    engineers = max((e.engineers for e in efforts), default=0)
    weeks = sum(e.weeks for e in efforts)
    sized = (
        f"Sized {plural(len(efforts), 'phase')}: up to {plural(engineers, 'engineer')} for "
        f"{format_number(weeks)} weeks."
    )
    if estimate is None:
        summary = f"{sized} No day rate is stated, so the cost stays TO CONFIRM."
        out = "the effort. The cost needs a day rate the client confirms."
    else:
        summary = f"{sized} Code has the final word on the cost."
        out = f"the locked cost, {format_money(estimate.total, estimate.currency)}."
    return with_text(
        step, summary, received_line(AGENT_ID, "the design phases."), passed_line(AGENT_ID, out)
    )
