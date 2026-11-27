"""Per-request wiring: the run mode, the live model and today's date. Tests override these."""

from datetime import date

from config import RunMode
from llm.client import Runtime
from llm.gateway import GatewayModel
from llm.modes import choose_mode


def current_mode() -> RunMode:
    return choose_mode()


def make_runtime() -> Runtime:
    return Runtime(model=GatewayModel.from_env(), lite=current_mode() == "lite")


def today() -> date:
    return date.today()
