"""Stages 1 and 2 through the real endpoints, with the scripted fake model in place of Gemini."""

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import app
from llm.client import Runtime
from llm.fake import FakeChatModel, FakeStep, fail, reply_json, reply_text, reply_tool
from services import runtime as wiring
from tests.fixtures import briefs

TODAY = date(2026, 11, 28)

NORTHWIND_CASE = {
    "is_brief": True,
    "goals": ["fewer status calls", "status online any time"],
    "warnings": [
        {"text": "tight budget", "quote": "Budget is tight this year"},
        {"text": "invented worry", "quote": "the board hates risk"},
    ],
    "rate": {"amount": 600, "currency": "USD", "unit": "engineer-day"},
    "team": {"engineers": 2, "weeks": 4},
    "start": "2026-12-07",
    "peak": "early January",
    "flags": {
        "personal_data": True,
        "existing_systems": True,
        "contract_type": "tm",
        "function": "Claims Operations",
        "seniority": "large",
    },
}
DESIGN = {
    "parts": [
        {"name": "Status page", "purpose": "Customer looks up a claim"},
        {"name": "Read-only copy", "purpose": "Claim data for the page"},
        {"name": "Secure link", "purpose": "Sent by email"},
    ],
    "integrations": [{"system": "claims system", "how": "nightly copy", "read_only": True}],
    "phases": [
        {"no": 1, "name": "Status page", "scope": ["lookup"]},
        {"no": 2, "name": "Secure link", "scope": ["link"]},
    ],
    "out_of_scope": ["claim filing"],
}
SIZING = {
    "phases": [{"no": 1, "engineers": 2, "weeks": 2}, {"no": 2, "engineers": 2, "weeks": 2}],
    "day_rate": 600,
    "start": "2026-12-07",
    "notes": "Matches the planned team.",
}
CLAIMS = {
    "claims": [
        {
            "section": "executive_summary",
            "text": "A self-service claim status page.",
            "origin": "proposal",
        },
        {
            "section": "client_situation",
            "text": "Budget is tight.",
            "origin": "brief",
            "quote": "Budget is tight this year",
        },
        {
            "section": "client_situation",
            "text": "The board loves us.",
            "origin": "brief",
            "quote": "the board loves us",
        },
        {"section": "risks", "text": "Saves $90,000 a year.", "origin": "proposal"},
        {"section": "team_cost", "text": "Costs $1.", "origin": "calculated"},
    ]
}


class Scripted:
    """Installs a fake model script for the next request and records what it was asked."""

    def __init__(self) -> None:
        self.model = FakeChatModel([])

    def load(self, script: list[FakeStep]) -> FakeChatModel:
        self.model = FakeChatModel(script)
        return self.model


async def no_wait(seconds: float) -> None:
    return None


@pytest.fixture
def scripted() -> Iterator[Scripted]:
    holder = Scripted()
    app.dependency_overrides[wiring.make_runtime] = lambda: Runtime(
        model=holder.model, sleep=no_wait
    )
    app.dependency_overrides[wiring.today] = lambda: TODAY
    app.dependency_overrides[wiring.current_mode] = lambda: "full"
    yield holder
    app.dependency_overrides.clear()


client = TestClient(app)


def form(brief: str = briefs.NORTHWIND, **changes: object) -> dict[str, Any]:
    return {
        "client": "Northwind Insurance",
        "country": "Germany",
        "brief": brief,
        "confirmed_fake": True,
    } | changes


def discover_northwind(scripted: Scripted) -> dict[str, Any]:
    scripted.load([reply_json(NORTHWIND_CASE)])
    response = client.post("/api/discover", json=form())
    assert response.status_code == 200
    return response.json()


def state_from(discovered: dict[str, Any]) -> dict[str, Any]:
    keys = ("run_id", "mode", "brief", "case_file", "flags", "board_plan", "steps")
    return {key: discovered[key] for key in keys}


def draft_script(sizing: dict[str, Any] = SIZING) -> list[FakeStep]:
    tool_args = {"phases": [{"no": 1, "people": 2, "days": 10}], "rate": 600}
    return [
        reply_json(DESIGN),
        reply_tool("cost_calculator", tool_args),
        reply_json(sizing),
        reply_json(CLAIMS),
    ]


# --- Stage 1: discover ---


def test_discover_returns_case_file_board_and_code_written_step(scripted: Scripted) -> None:
    body = discover_northwind(scripted)
    assert [s["id"] for s in body["board_plan"]["seats"]] == [
        "cfo",
        "vp_director",
        "enterprise_architect",
        "procurement",
        "security",
    ]
    assert body["board_plan"]["seats"][1]["title"] == "VP, Claims Operations"
    assert body["case_file"]["client"] == "Northwind Insurance"
    assert [w["text"] for w in body["case_file"]["warnings"]] == ["tight budget"]
    assert [w["text"] for w in body["ignored_signals"]] == ["invented worry"]
    assert body["checks"] == {"real_data": "passed", "injection": "passed", "is_brief": True}
    step = body["steps"][0]
    assert step["agent"] == "business_analyst" and step["tier"] == "haiku"
    assert "Code dropped 1 signal" in step["summary"]
    assert step["handoff_in"].startswith("Received from You: the brief (")
    assert step["handoff_out"] == (
        "Hands to Solution Architect and Board composer: the case file. "
        "The 5 flags choose the board."
    )


def test_the_brief_reaches_the_model_only_inside_the_marked_block(scripted: Scripted) -> None:
    discover_northwind(scripted)
    user_message = scripted.model.requests[0].messages[1]["content"]
    assert "<client_brief>\n" + briefs.NORTHWIND + "\n</client_brief>" in user_message


def test_not_a_brief_stops_after_the_business_analyst(scripted: Scripted) -> None:
    model = scripted.load([reply_json({"is_brief": False})])
    response = client.post("/api/discover", json=form(briefs.NOT_A_BRIEF))
    assert response.json() == {
        "error": "not_a_brief",
        "message": "This does not look like a client brief.",
    }
    assert len(model.requests) == 1


def test_real_data_is_stopped_before_any_ai_call(scripted: Scripted) -> None:
    model = scripted.load([])
    response = client.post("/api/discover", json=form(briefs.HOSTILE_REAL_DATA))
    assert response.status_code == 422
    assert response.json()["error"] == "input_blocked"
    assert "07700" not in response.text and "gmail" not in response.text
    assert model.requests == []


def test_too_long_brief_is_refused_with_its_limit(scripted: Scripted) -> None:
    scripted.load([])
    response = client.post("/api/discover", json=form("a" * 15_001))
    assert response.status_code == 422
    assert response.json()["error"] == "too_long"


def test_injection_gives_a_notice_and_continues(scripted: Scripted) -> None:
    scripted.load([reply_json(NORTHWIND_CASE)])
    response = client.post("/api/discover", json=form(briefs.HOSTILE_INJECTION))
    body = response.json()
    assert body["checks"]["injection"] == "notice"
    assert body["notices"]


def test_broken_key_gives_a_friendly_error_not_a_crash(scripted: Scripted) -> None:
    scripted.load([fail("auth")])
    body = client.post("/api/discover", json=form()).json()
    assert body["error"] == "budget_used_up"
    assert "key" not in body["message"].lower()


def test_model_that_keeps_failing_gives_step_failed(scripted: Scripted) -> None:
    scripted.load([fail("server")] * 3)
    assert client.post("/api/discover", json=form()).json()["error"] == "step_failed"


def test_bad_json_every_time_gives_step_failed(scripted: Scripted) -> None:
    scripted.load([reply_text("not json")] * 4)
    assert client.post("/api/discover", json=form()).json()["error"] == "step_failed"


def test_a_malformed_request_gets_the_error_shape(scripted: Scripted) -> None:
    response = client.post("/api/discover", json={"brief": 5})
    assert response.status_code == 422
    assert set(response.json()) == {"error", "message"}


# --- Stage 2: draft ---


def test_draft_runs_three_agents_and_code_checks_every_claim(scripted: Scripted) -> None:
    state = state_from(discover_northwind(scripted))
    model = scripted.load(draft_script())
    response = client.post("/api/draft", json=state)
    assert response.status_code == 200
    body = response.json()

    assert body["estimate"]["total"] == 24000
    assert body["schedule"]["go_live"] == "2027-01-04"
    claims = {c["id"]: c for c in body["claims"]}
    texts = [c["text"] for c in body["claims"]]
    assert "Total: 40 engineer-days, $24,000." in texts
    assert claims["C2"]["origin"] == "brief"  # real quote kept
    assert claims["C3"]["origin"] == "assumption"  # invented quote re-tagged
    assert claims["C4"]["origin"] == "assumption"  # invented $90,000 re-tagged
    assert claims["C5"]["origin"] == "derived"  # a model cannot write "calculated"
    assert body["retagged"] == ["C3", "C4"]
    assert all(c["locked"] for c in body["claims"] if c["origin"] == "calculated")

    agents = [s["agent"] for s in body["steps"]]
    assert agents == ["solution_architect", "delivery_manager", "proposal_manager"]
    architect, delivery, proposal = body["steps"]
    assert architect["handoff_out"] == "Hands to Delivery Manager: the 3-part design."
    assert delivery["tool_calls"][0]["tool"] == "cost_calculator"
    assert delivery["tool_calls"][0]["result"]["total"] == 12000
    assert delivery["handoff_out"] == "Hands to Proposal Manager: the locked cost, $24,000."
    assert proposal["handoff_in"].startswith("Received from Delivery Manager:")
    assert "Code re-tagged 2 claims TO CONFIRM." in proposal["summary"]
    assert len(model.requests) == 4


def test_draft_inputs_never_include_the_full_brief(scripted: Scripted) -> None:
    state = state_from(discover_northwind(scripted))
    model = scripted.load(draft_script())
    client.post("/api/draft", json=state)
    for request in model.requests:
        assert "<client_brief>" not in request.messages[1]["content"]


def test_a_rate_the_brief_does_not_state_leaves_the_cost_to_confirm(scripted: Scripted) -> None:
    state = state_from(discover_northwind(scripted))
    state["case_file"]["rate"] = None
    scripted.load(draft_script(SIZING | {"day_rate": 999}))
    body = client.post("/api/draft", json=state).json()
    assert body["estimate"] is None
    assert any("the day rate and team size" in c["text"] for c in body["claims"])


def test_draft_rechecks_the_brief_from_the_browser(scripted: Scripted) -> None:
    state = state_from(discover_northwind(scripted))
    state["brief"] = briefs.HOSTILE_REAL_DATA
    model = scripted.load(draft_script())
    response = client.post("/api/draft", json=state)
    assert response.json()["error"] == "input_blocked"
    assert model.requests == []


def test_draft_without_a_case_file_asks_to_start_again(scripted: Scripted) -> None:
    state = state_from(discover_northwind(scripted)) | {"case_file": None}
    scripted.load([])
    body = client.post("/api/draft", json=state).json()
    assert body["error"] == "step_failed" and "start again" in body["message"]


def test_a_failed_architect_fails_the_stage_with_a_retry(scripted: Scripted) -> None:
    state = state_from(discover_northwind(scripted))
    scripted.load([fail("server")] * 3)
    assert client.post("/api/draft", json=state).json()["error"] == "step_failed"


def test_not_a_brief_with_null_lists_still_stops_cleanly(scripted: Scripted) -> None:
    # Seen live: a model answers a non-brief with "goals": null instead of an empty list.
    reply = {"is_brief": False, "goals": None, "warnings": None, "rate": None, "flags": {}}
    model = scripted.load([reply_json(reply)])
    body = client.post("/api/discover", json=form(briefs.NOT_A_BRIEF)).json()
    assert body["error"] == "not_a_brief"
    assert len(model.requests) == 1
