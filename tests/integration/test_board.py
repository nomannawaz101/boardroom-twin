"""Stage 3 through the real endpoints, with the scripted fake model in place of a live one.

With the fake model, seat calls run in board-plan order, so each script line maps to a seat.
"""

from typing import Any

from fastapi.testclient import TestClient

from app import app
from domain.board_composer import compose_board
from llm.fake import FakeStep, fail, reply_json, reply_text
from schemas.case_file import BoardFlags
from tests.integration.conftest import Scripted

client = TestClient(app)

NORTHWIND_FLAGS = {
    "personal_data": True,
    "existing_systems": True,
    "contract_type": "tm",
    "function": "Claims Operations",
    "seniority": "large",
}
HARBOR_FLAGS = {
    "personal_data": False,
    "existing_systems": False,
    "contract_type": "tm",
    "function": "Support Operations",
    "seniority": "small",
}

CFO = {
    "ratings": [
        {"criterion": "cost_clarity", "rating": 7, "reason": "clear"},
        {"criterion": "value", "rating": 5, "reason": "ok"},
        {"criterion": "budget_fit", "rating": 3, "reason": "tight"},
    ],
    "objections": [
        {
            "claim_id": "C2",
            "text": "No smaller first step",
            "severity": "blocker",
            "resolve_hint": "Split into two phases",
        }
    ],
    "quote": "Is there a smaller first step?",
}
ARCHITECT = {
    "ratings": [
        {"criterion": "system_fit", "rating": 7},
        {"criterion": "risk_recovery", "rating": 4},
        {"criterion": "maintainability", "rating": 8},
    ],
    "objections": [{"claim_id": "C99", "text": "No rollback plan"}],
    "quote": "Show me the rollback.",
}
VP = {
    "ratings": [
        {"criterion": "customer_benefit", "rating": 9},
        {"criterion": "timing", "rating": 5},
        {"criterion": "disruption", "rating": 7},
    ],
    "objections": [{"claim_id": "C3", "text": "January peak", "severity": "condition"}],
    "quote": "Not in our busiest week.",
}
PROCUREMENT = {
    "items": [
        {"id": "pricing_model", "status": "met", "reason": "stated"},
        {"id": "change_control", "status": "partly", "reason": "vague"},
        {"id": "acceptance_payment", "status": "partly", "reason": "no milestones"},
    ],
    "objections": [{"item_id": "change_control", "text": "No change process"}],
    "quote": "Show me change control.",
}
SECURITY = {
    "items": [
        {"id": "data_protection", "status": "partly"},
        {"id": "access_control", "status": "not_met", "reason": "not described"},
        {"id": "data_rules_fit", "status": "partly"},
    ],
    "objections": [
        {"item_id": "data_rules_fit", "text": "Retention rule unknown", "needs_client": True}
    ],
    "quote": "Who can see a claim?",
}
NORTHWIND_ANSWERS = [CFO, VP, ARCHITECT, PROCUREMENT, SECURITY]  # board-plan order


def state(flags: dict[str, Any] = NORTHWIND_FLAGS, **changes: object) -> dict[str, Any]:
    plan = compose_board(BoardFlags.model_validate(flags))
    claims = [
        {
            "id": "C1",
            "section": "executive_summary",
            "text": "A claim status page.",
            "origin": "proposal",
        },
        {
            "id": "C2",
            "section": "team_cost",
            "text": "Total: $24,000.",
            "origin": "calculated",
            "locked": True,
        },
        {
            "id": "C3",
            "section": "timeline",
            "text": "Go-live: Mon Jan 4, 2027.",
            "origin": "calculated",
            "locked": True,
        },
        {
            "id": "C4",
            "section": "assumptions",
            "text": "Confirm with the client: holidays.",
            "origin": "assumption",
        },
    ]
    base = {
        "run_id": "run1",
        "mode": "full",
        "brief": "brief text",
        "draft_no": 1,
        "case_file": {
            "client": "Northwind Insurance",
            "country": "Germany",
            "is_brief": True,
            "goals": ["fewer calls"],
            "warnings": [{"text": "tight budget", "quote": "q"}],
            "flags": flags,
        },
        "flags": flags,
        "board_plan": plan.model_dump(),
        "claims": claims,
    }
    return base | changes


def review(
    scripted: Scripted, script: list[FakeStep], body: dict[str, Any] | None = None
) -> dict[str, Any]:
    scripted.load(script)
    return client.post("/api/board", json=body or state()).json()


# --- A full round ---


def test_northwind_round_one_is_decided_by_code(scripted: Scripted) -> None:
    body = review(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS])
    seats = body["round"]["seats"]
    assert [(s["seat_id"], s["score"], s["decision"], s["able"]) for s in seats] == [
        ("cfo", 5.3, "Rejected", False),
        ("vp_director", 7.1, "Yes, with a condition", True),
        ("enterprise_architect", 6.2, "Rejected", False),
        ("procurement", None, "Pass, with conditions", True),
        ("security", None, "Blocked", False),
    ]
    assert body["round"]["progress"] == {"able": 2, "total": 5}
    assert seats[1]["title"] == "VP, Claims Operations"
    tracker = [(t["id"], t["seat"], t["severity"], t["claim_ids"]) for t in body["tracker"]]
    assert tracker == [
        ("O1", "cfo", "blocker", ["C2"]),
        ("O2", "vp_director", "condition", ["C3"]),
        ("O3", "enterprise_architect", "blocker", []),  # unknown claim id C99 dropped
        ("O4", "procurement", "condition", []),
        ("O5", "procurement", "condition", []),
        ("O6", "security", "condition", []),
        ("O7", "security", "blocker", []),
        ("C1", "security", "condition", []),
    ]
    assert body["tracker"][0]["resolve_hint"] == "Split into two phases"


def test_seat_steps_show_tier_badge_and_code_written_summary(scripted: Scripted) -> None:
    body = review(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS])
    steps = {s["agent"]: s for s in body["steps"]}
    assert [s["stage"] for s in body["steps"]] == [3] * 5
    assert (steps["cfo"]["tier"], steps["cfo"]["badge"]) == ("sonnet", "fake-main")
    assert (steps["security"]["tier"], steps["security"]["badge"]) == ("haiku", "fake-fast")
    assert steps["cfo"]["summary"] == (
        "Rated 3 criteria. Code scored 5.30 against the 7.0 needed: Rejected."
    )
    assert steps["procurement"]["summary"] == (
        "Answered 3 of 3 checklist items. Code decided: Pass, with conditions."
    )
    assert steps["cfo"]["handoff_in"] == "Received from Proposal Manager: draft 1, 4 claims."


def test_seats_get_the_proposal_and_their_terms_as_data_not_the_brief(scripted: Scripted) -> None:
    review(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS])
    vp_request = scripted.model.requests[1]
    system, user = vp_request.messages[0]["content"], vp_request.messages[1]["content"]
    assert "VP, Claims Operations" not in system  # the brief-made title stays out of the prompt
    assert '"your_seat": "VP, Claims Operations"' in user
    assert '"customer_benefit"' in user and '"tag": "CALCULATED"' in user
    assert "brief text" not in user and "<client_brief>" not in user


def test_only_planned_seats_run_and_count(scripted: Scripted) -> None:
    body = review(
        scripted, [reply_json(CFO), reply_json(VP), reply_json(PROCUREMENT)], state(HARBOR_FLAGS)
    )
    assert [s["seat_id"] for s in body["round"]["seats"]] == ["cfo", "vp_director", "procurement"]
    assert len(scripted.model.requests) == 3
    assert body["round"]["progress"]["total"] == 3


# --- Not reviewed ---


def test_a_failed_scoring_seat_is_not_reviewed_and_the_others_still_count(
    scripted: Scripted,
) -> None:
    script = [
        reply_json(CFO),
        reply_json(VP),
        fail("server"),
        fail("server"),
        fail("server"),
        reply_json(PROCUREMENT),
        reply_json(SECURITY),
    ]
    body = review(scripted, script)
    seats = {s["seat_id"]: s for s in body["round"]["seats"]}
    architect = seats["enterprise_architect"]
    assert (architect["status"], architect["able"], architect["decision"], architect["score"]) == (
        "not_reviewed",
        False,
        "Not reviewed",
        None,
    )
    assert seats["cfo"]["decision"] == "Rejected" and seats["vp_director"]["able"] is True
    assert body["round"]["progress"] == {"able": 2, "total": 5}
    step = next(s for s in body["steps"] if s["agent"] == "enterprise_architect")
    assert step["status"] == "not_reviewed" and "not_reviewed" in step["flags"]
    assert "Not reviewed" in step["summary"] and step["attempts"] == 3


def test_a_failed_gate_seat_is_not_reviewed(scripted: Scripted) -> None:
    script = [reply_json(a) for a in NORTHWIND_ANSWERS[:4]] + [reply_text("not json")] * 4
    body = review(scripted, script)
    security = body["round"]["seats"][4]
    assert (security["seat_id"], security["status"], security["able"]) == (
        "security",
        "not_reviewed",
        False,
    )
    assert not any(t["seat"] == "security" for t in body["tracker"])


def test_fewer_than_two_answers_stops_the_run_with_a_retry(scripted: Scripted) -> None:
    script: list[FakeStep] = [reply_json(CFO)] + [reply_text("nope")] * 16
    body = review(scripted, script)
    assert body["error"] == "step_failed" and "Fewer than 2" in body["message"]


# --- Retry this seat ---


def test_retrying_a_seat_recomputes_the_round_and_keeps_tracker_ids(scripted: Scripted) -> None:
    first = review(
        scripted,
        [
            reply_json(CFO),
            reply_json(VP),
            fail("server"),
            fail("server"),
            fail("server"),
            reply_json(PROCUREMENT),
            reply_json(SECURITY),
        ],
    )
    retry_state = state(rounds=[first["round"]], tracker=first["tracker"])
    scripted.load([reply_json(ARCHITECT)])
    body = client.post(
        "/api/board/retry", json={"state": retry_state, "seat_id": "enterprise_architect"}
    ).json()
    seats = {s["seat_id"]: s for s in body["round"]["seats"]}
    assert (seats["enterprise_architect"]["score"], seats["enterprise_architect"]["decision"]) == (
        6.2,
        "Rejected",
    )
    assert body["round"]["progress"] == {"able": 2, "total": 5}
    assert [t["id"] for t in body["tracker"]][-1] == "O7"  # appended after O1..O6 and C1
    assert [s["agent"] for s in body["steps"]] == ["enterprise_architect"]


def test_only_a_not_reviewed_seat_can_be_retried(scripted: Scripted) -> None:
    first = review(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS])
    retry_state = state(rounds=[first["round"]], tracker=first["tracker"])
    model = scripted.load([])
    body = client.post("/api/board/retry", json={"state": retry_state, "seat_id": "cfo"}).json()
    assert body["error"] == "input_blocked" and model.requests == []


def test_a_board_without_a_draft_asks_for_the_draft_first(scripted: Scripted) -> None:
    body = review(scripted, [], state(claims=[]))
    assert body["error"] == "step_failed" and "no draft" in body["message"]


# Appended to tests/integration/test_board.py: gate answers that leave a checklist item out.

SECURITY_MISSING_ONE = {
    "items": [
        {"id": "data_protection", "status": "met"},
        {"id": "data_rules_fit", "status": "met"},
    ],
    "quote": "Looks fine.",
}
SECURITY_MISSING_ONE_MUST_NOT_MET = {
    "items": [
        {"id": "data_protection", "status": "not_met", "reason": "not described"},
        {"id": "data_rules_fit", "status": "met"},
    ],
    "quote": "Nothing on data protection.",
}
SECURITY_COMPLETE = {
    "items": [
        {"id": "data_protection", "status": "met"},
        {"id": "access_control", "status": "met"},
        {"id": "data_rules_fit", "status": "met"},
    ],
    "quote": "All covered.",
}


def gate_script(*security_replies: dict[str, Any]) -> list[FakeStep]:
    """CFO, VP, Architect and Procurement answer once; then the Security Officer's replies."""
    return [reply_json(a) for a in NORTHWIND_ANSWERS[:4]] + [
        reply_json(r) for r in security_replies
    ]


def security_of(body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    seat = next(s for s in body["round"]["seats"] if s["seat_id"] == "security")
    step = next(s for s in body["steps"] if s["agent"] == "security")
    return seat, step


def test_a_gate_reply_missing_an_item_is_retried_with_the_item_named(scripted: Scripted) -> None:
    review(scripted, gate_script(SECURITY_MISSING_ONE, SECURITY_COMPLETE))
    retry_message = scripted.model.requests[-1].messages[-1]["content"]
    assert "missing: access_control" in retry_message


def test_one_item_missing_and_the_rest_met_is_not_reviewed_with_a_partial_answer(
    scripted: Scripted,
) -> None:
    body = review(scripted, gate_script(*[SECURITY_MISSING_ONE] * 4))
    seat, step = security_of(body)
    assert (seat["status"], seat["partial"], seat["able"], seat["outcome"]) == (
        "not_reviewed",
        True,
        False,
        None,
    )
    assert [i["status"] for i in seat["items"]] == ["met", "missing", "met"]
    assert (step["status"], step["attempts"]) == ("not_reviewed", 4)
    assert "partial" in step["flags"] and "not_reviewed" in step["flags"]
    assert "Answered only 2 of 3 checklist items" in step["summary"]
    assert not any(t["seat"] == "security" for t in body["tracker"])
    assert body["verdict"]["label"] == "Not ready yet"  # the CFO's known rejection wins


def test_one_item_missing_and_a_must_have_not_met_is_blocked(scripted: Scripted) -> None:
    body = review(scripted, gate_script(*[SECURITY_MISSING_ONE_MUST_NOT_MET] * 4))
    seat, step = security_of(body)
    assert (seat["status"], seat["outcome"], seat["decision"], seat["partial"]) == (
        "answered",
        "blocked",
        "Blocked",
        True,
    )
    assert [i["status"] for i in seat["items"]] == ["not_met", "missing", "met"]
    assert step["status"] == "retried" and "skipped" not in step["flags"]
    assert "partial" in step["flags"]
    assert [t["item_id"] for t in body["tracker"] if t["seat"] == "security"] == ["data_protection"]


def test_one_item_missing_then_fixed_by_the_retry_counts_normally(scripted: Scripted) -> None:
    body = review(scripted, gate_script(SECURITY_MISSING_ONE, SECURITY_COMPLETE))
    seat, step = security_of(body)
    assert (seat["status"], seat["outcome"], seat["partial"], seat["able"]) == (
        "answered",
        "pass",
        False,
        True,
    )
    assert (step["status"], step["attempts"]) == ("retried", 2)
    assert "partial" not in step["flags"]


def test_review_incomplete_when_only_a_partial_gate_is_unresolved(scripted: Scripted) -> None:
    passing_cfo = CFO | {
        "ratings": [{"criterion": c, "rating": 9} for c in ("cost_clarity", "value", "budget_fit")],
        "objections": [],
    }
    passing_vp = VP | {
        "ratings": [
            {"criterion": c, "rating": 9} for c in ("customer_benefit", "timing", "disruption")
        ],
        "objections": [],
    }
    passing_ea = ARCHITECT | {
        "ratings": [
            {"criterion": c, "rating": 9}
            for c in ("system_fit", "risk_recovery", "maintainability")
        ],
        "objections": [],
    }
    procurement_pass = {
        "items": [
            {"id": i, "status": "met"}
            for i in ("pricing_model", "change_control", "acceptance_payment")
        ]
    }
    script = [
        reply_json(passing_cfo),
        reply_json(passing_vp),
        reply_json(passing_ea),
        reply_json(procurement_pass),
    ] + [reply_json(SECURITY_MISSING_ONE)] * 4
    body = review(scripted, script)
    assert body["verdict"] == {"code": "review_incomplete", "label": "Review incomplete"}


def test_retrying_a_partial_gate_that_now_answers_in_full(scripted: Scripted) -> None:
    first = review(scripted, gate_script(*[SECURITY_MISSING_ONE] * 4))
    retry_state = state(rounds=[first["round"]], tracker=first["tracker"])
    scripted.load([reply_json(SECURITY_COMPLETE)])
    body = client.post(
        "/api/board/retry", json={"state": retry_state, "seat_id": "security"}
    ).json()
    seat, _ = security_of(body)
    assert (seat["status"], seat["outcome"], seat["partial"]) == ("answered", "pass", False)
