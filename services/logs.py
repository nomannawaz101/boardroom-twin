"""Structured run logs (guard G15): ids, timings, tokens and codes. Never brief or model text."""

import logging

from schemas.step import StepRecord

log = logging.getLogger("boardroom")


def log_step(run_id: str, step: StepRecord) -> None:
    log.info(
        "run=%s stage=%d agent=%s status=%s ms=%d tokens_in=%d tokens_out=%d attempts=%d",
        run_id,
        step.stage,
        step.agent,
        step.status,
        step.duration_ms,
        step.tokens_in,
        step.tokens_out,
        step.attempts,
    )


def log_error(run_id: str, code: str) -> None:
    log.warning("run=%s error=%s", run_id, code)
