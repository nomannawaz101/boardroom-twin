import json

import pytest

import config
from agents.registry import AGENTS, NODE_LABELS, node_label, registered_count
from domain.seats import SEATS, SEATS_BY_ID
from llm.modes import choose_mode
from llm.usage import cost_usd
from tools.registry import TOOLS, ToolContext, run_tool


def call(name: str, args: object, brief: str = "") -> tuple[dict[str, object], bool]:
    outcome = run_tool(name, json.dumps(args), ToolContext(brief=brief))
    return outcome.result, outcome.ok


# --- Tools ---


def test_cost_calculator_per_phase_and_total() -> None:
    result, ok = call(
        "cost_calculator",
        {
            "phases": [{"no": 1, "people": 2, "days": 10}, {"no": 2, "people": 2, "days": 10}],
            "rate": 600,
        },
    )
    assert ok
    assert result == {
        "phases": [{"no": 1, "cost": 12000.0}, {"no": 2, "cost": 12000.0}],
        "engineer_days": 40,
        "total": 24000.0,
        "currency": "USD",
    }


@pytest.mark.parametrize(
    "args",
    [
        {"phases": [], "rate": 600},
        {"phases": [{"no": 1, "people": 0, "days": 10}], "rate": 600},
        {"phases": [{"no": 1, "people": 2, "days": 10}], "rate": -5},
        {"rate": 600},
        [1, 2],
    ],
)
def test_cost_calculator_bad_input_is_an_error_result_not_a_crash(args: object) -> None:
    assert call("cost_calculator", args) == ({"error": "invalid_arguments"}, False)


def test_tool_arguments_that_are_not_json() -> None:
    outcome = run_tool("working_days", "{not json", ToolContext())
    assert (outcome.ok, outcome.result) == (False, {"error": "invalid_arguments"})


def test_unknown_tool() -> None:
    assert call("web_search", {}) == ({"error": "unknown_tool"}, False)


def test_quote_checker() -> None:
    brief = "Claim calls peak in early January."
    assert call("quote_checker", {"quote": "claim calls  peak"}, brief) == ({"found": True}, True)
    assert call("quote_checker", {"quote": "peak in March"}, brief) == ({"found": False}, True)


def test_working_days_tool_with_holidays() -> None:
    args = {"start": "2026-12-21", "end": "2026-12-25", "holidays": ["2026-12-25"]}
    assert call("working_days", args) == ({"working_days": 4}, True)


def test_every_tool_schema_names_itself() -> None:
    for name, spec in TOOLS.items():
        assert spec.schema["function"]["name"] == name  # type: ignore[index]


# --- Agent and seat registries ---


def test_fourteen_roles_are_registered() -> None:
    assert registered_count() == 14
    assert {s.id for s in SEATS} <= set(AGENTS)


def test_every_agent_is_routed_to_a_tier() -> None:
    assert set(config.MODEL_ROUTING) == set(AGENTS)
    assert AGENTS["business_analyst"].tier == "haiku"
    assert AGENTS["procurement"].tier == "haiku" and AGENTS["security"].tier == "haiku"
    assert AGENTS["proposal_manager"].tier == "sonnet"


def test_handoffs_point_at_known_nodes() -> None:
    known = set(AGENTS) | set(NODE_LABELS)
    for agent in AGENTS.values():
        assert set(agent.receives_from) | set(agent.passes_to) <= known
        assert all(node_label(n) for n in agent.receives_from + agent.passes_to)


def test_extras_name_a_feature_switch() -> None:
    for agent in AGENTS.values():
        assert agent.feature is None or agent.feature in config.FEATURES


def test_scoring_weights_sum_to_one_and_gates_have_two_musts() -> None:
    for seat in SEATS:
        if seat.kind == "scoring":
            assert sum(c.weight for c in seat.criteria) == pytest.approx(1.0)
            assert seat.needed_score is not None and len(seat.criteria) == 3
        else:
            assert len(seat.checklist) == 3
            assert sum(item.must for item in seat.checklist) == 2


def test_seat_needed_scores() -> None:
    needed = {s.id: s.needed_score for s in SEATS if s.kind == "scoring"}
    assert needed == {"cfo": 7.0, "vp_director": 7.0, "enterprise_architect": 8.0}
    assert SEATS_BY_ID["security"].checklist[1].id == "access_control"


# --- Usage and modes ---


def test_cost_from_the_price_table() -> None:
    assert cost_usd("sonnet", 1_000_000, 100_000) == 3.0
    assert cost_usd("haiku", 1_000_000, 1_000_000) == 0.6


@pytest.mark.parametrize(
    ("env", "mode"), [("auto", "full"), ("lite", "lite"), ("sample", "sample")]
)
def test_choose_mode(monkeypatch: pytest.MonkeyPatch, env: str, mode: str) -> None:
    monkeypatch.setenv("RUN_MODE", env)
    assert choose_mode() == mode
