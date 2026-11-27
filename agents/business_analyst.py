"""Business Analyst (Haiku): is this a brief? Writes the case file and the 5 board flags."""

from datetime import date

from agents.common import inputs_block, plural, system_prompt, with_text
from agents.registry import passed_line, received_line
from guards.input import CheckedInput
from llm.client import AgentResult, Runtime, run_agent
from schemas.case_file import BoardFlags, CaseFile
from schemas.step import StepRecord

AGENT_ID = "business_analyst"
FLAG_COUNT = len(BoardFlags.model_fields)


async def run(checked: CheckedInput, today: date, runtime: Runtime) -> AgentResult[CaseFile]:
    user = "\n".join(
        [
            inputs_block(
                {"today": today.isoformat(), "client": checked.client, "country": checked.country}
            ),
            checked.wrapped_brief,
        ]
    )
    return await run_agent(AGENT_ID, system_prompt(AGENT_ID), user, CaseFile, runtime=runtime)


def describe(step: StepRecord, case_file: CaseFile, dropped: int, brief_chars: int) -> StepRecord:
    summary = (
        f"Read the brief once. Wrote a case file with {plural(len(case_file.goals), 'goal')} "
        f"and {plural(len(case_file.warnings), 'warning sign')}, each backed by an exact quote, "
        f"and set {FLAG_COUNT} context flags."
    )
    if dropped:
        summary += f" Code dropped {plural(dropped, 'signal')} whose quote is not in the brief."
    return with_text(
        step,
        summary,
        received_line(AGENT_ID, f"the brief ({brief_chars:,} characters), checked by code first."),
        passed_line(AGENT_ID, f"the case file. The {FLAG_COUNT} flags choose the board."),
    )
