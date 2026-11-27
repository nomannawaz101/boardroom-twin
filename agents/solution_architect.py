"""Solution Architect (Sonnet): parts, integrations and phases. No cost and no dates."""

from agents.common import dump, inputs_block, plural, system_prompt, with_text
from agents.registry import passed_line, received_line
from llm.client import AgentResult, Runtime, run_agent
from schemas.answers import SolutionArchitectAnswer
from schemas.case_file import CaseFile
from schemas.step import StepRecord

AGENT_ID = "solution_architect"


async def run(case_file: CaseFile, runtime: Runtime) -> AgentResult[SolutionArchitectAnswer]:
    user = inputs_block({"case_file": dump(case_file)})
    return await run_agent(
        AGENT_ID,
        system_prompt(AGENT_ID),
        user,
        SolutionArchitectAnswer,
        runtime=runtime,
        default=SolutionArchitectAnswer(),
    )


def describe(step: StepRecord, design: SolutionArchitectAnswer) -> StepRecord:
    parts = plural(len(design.parts), "part")
    summary = (
        f"Designed the solution in {parts}, with {plural(len(design.integrations), 'integration')} "
        f"and {plural(len(design.phases), 'delivery phase')}."
    )
    return with_text(
        step,
        summary,
        received_line(AGENT_ID, "the case file, not the full brief."),
        passed_line(AGENT_ID, f"the {len(design.parts)}-part design."),
    )
