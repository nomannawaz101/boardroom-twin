"""Agent registry: every role, its tier, stage and handoffs. The count shown in the app comes
from here, so it can never overstate (plan section 1).

Handoff lines on screen are built by code from these entries, never written by a model.
"""

from dataclasses import dataclass

import config
from domain.seats import SEATS

USER = "user"
BOARD_COMPOSER = "board_composer"
CLIENT_BOARD = "client_board"
REPORT = "report"

# Steps that are not agents but appear in handoff lines.
NODE_LABELS: dict[str, str] = {
    USER: "You",
    BOARD_COMPOSER: "Board composer",
    CLIENT_BOARD: "Client board",
    REPORT: "Report",
}


@dataclass(frozen=True)
class AgentSpec:
    id: str
    label: str
    stage: int
    receives_from: tuple[str, ...]
    passes_to: tuple[str, ...]
    feature: str | None = None  # None = core; otherwise the FEATURES switch that enables it

    @property
    def tier(self) -> config.Tier:
        return config.MODEL_ROUTING[self.id]


PROPOSAL_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        "business_analyst",
        "Business Analyst",
        1,
        (USER,),
        ("solution_architect", BOARD_COMPOSER),
    ),
    AgentSpec(
        "solution_architect",
        "Solution Architect",
        2,
        ("business_analyst",),
        ("delivery_manager", "risk_analyst"),
    ),
    AgentSpec(
        "delivery_manager",
        "Delivery Manager",
        2,
        ("solution_architect",),
        ("proposal_manager",),
    ),
    AgentSpec(
        "risk_analyst",
        "Risk & Compliance Analyst",
        2,
        ("solution_architect",),
        ("proposal_manager",),
        feature="risk_analyst",
    ),
    AgentSpec(
        "proposal_manager",
        "Proposal Manager",
        2,
        ("delivery_manager", "risk_analyst"),
        (CLIENT_BOARD,),
    ),
    AgentSpec("bid_manager", "Bid Manager", 4, (CLIENT_BOARD,), ("qa_reviewer", CLIENT_BOARD)),
    AgentSpec(
        "qa_reviewer", "QA Reviewer", 4, ("bid_manager",), (CLIENT_BOARD,), feature="qa_reviewer"
    ),
    AgentSpec(
        "presales_lead", "Presales Lead", 5, (CLIENT_BOARD,), (REPORT,), feature="meeting_prep"
    ),
    AgentSpec(
        "ux_designer", "UX Designer", 5, ("proposal_manager",), (REPORT,), feature="prototype"
    ),
)

SEAT_AGENTS: tuple[AgentSpec, ...] = tuple(
    AgentSpec(seat.id, seat.title, 3, ("proposal_manager",), (REPORT,)) for seat in SEATS
)

AGENTS: dict[str, AgentSpec] = {a.id: a for a in (*PROPOSAL_AGENTS, *SEAT_AGENTS)}


def get_agent(agent_id: str) -> AgentSpec:
    return AGENTS[agent_id]


def node_label(node_id: str) -> str:
    return AGENTS[node_id].label if node_id in AGENTS else NODE_LABELS[node_id]


def registered_count() -> int:
    return len(AGENTS)


def is_active(node_id: str) -> bool:
    """Non-agent nodes are always active; an agent behind a switch is active only when it is on."""
    agent = AGENTS.get(node_id)
    return agent is None or agent.feature is None or config.FEATURES.get(agent.feature, False)


def join_labels(node_ids: list[str]) -> str:
    labels = [node_label(n) for n in node_ids]
    return labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} and {labels[-1]}"


def received_line(agent_id: str, detail: str) -> str:
    """Handoff lines are built by code from the registry, never written by a model."""
    sources = [n for n in AGENTS[agent_id].receives_from if is_active(n)]
    return f"Received from {join_labels(sources)}: {detail}"


def passed_line(agent_id: str, detail: str) -> str:
    targets = [n for n in AGENTS[agent_id].passes_to if is_active(n)]
    return f"Hands to {join_labels(targets)}: {detail}"
