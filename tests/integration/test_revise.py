"""Stages 4 and 5 through the real endpoints, with the scripted fake model.

Each revise request calls the Bid Manager first, then every selected seat in board-plan order.
"""

from typing import Any

import pytest

from llm.fake import FakeStep, fail, reply_json, reply_text
from tests.integration.conftest import Scripted
from tests.integration.test_board import (
    ARCHITECT,
    CFO,
    HARBOR_FLAGS,
    NORTHWIND_ANSWERS,
    PROCUREMENT,
    VP,
    client,
    review,
    state,
)

ALL_MET_PROCUREMENT = {
    "items": [
        {"id": i, "status": "met"}
        for i in ("pricing_model", "change_control", "acceptance_payment")
    ]
}


def ratings(*values: float, seat: str = "cfo") -> list[dict[str, Any]]:
    names = {
        "cfo": ("cost_clarity", "value", "budget_fit"),
        "vp_director": ("customer_benefit", "timing", "disruption"),
        "enterprise_architect": ("system_fit", "risk_recovery", "maintainability"),
    }[seat]
    return [{"criterion": n, "rating": v} for n, v in zip(names, values, strict=True)]


def carry(base: dict[str, Any], board: dict[str, Any]) -> dict[str, Any]:
    """The browser's run state after a board vote."""
    return base | {
        "rounds": [board["round"]],
        "tracker": board["tracker"],
        "stop": board["stop"],
        "steps": board["steps"],
    }


def after_revision(current: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    return current | {
        "rounds": [*current["rounds"], body["round"]],
        "revisions": [*current.get("revisions", []), body["bid_round"]],
        "claims": body["claims"],
        "draft_no": body["draft_no"],
        "tracker": body["tracker"],
        "stop": body["stop"],
        "steps": [*current["steps"], *body["steps"]],
    }


def revise(
    scripted: Scripted, current: dict[str, Any], round_no: int, script: list[FakeStep]
) -> dict[str, Any]:
    scripted.load(script)
    return client.post("/api/revise", json={"state": current, "round_no": round_no}).json()


def report_of(current: dict[str, Any]) -> dict[str, Any]:
    return client.post("/api/report", json=current).json()["report"]


# --- A full Northwind loop: round 1, one Bid Manager round, everyone can proceed ---

BID_ROUND_ONE = {
    "changes": [
        {
            "objection_id": "O1",
            "action": "replace",
            "claim_id": "C1",
            "text": "Two phases: a status page first, updates later.",
        },
        {
            "objection_id": "O3",
            "action": "add",
            "claim_id": "C1",
            "text": "One switch turns the page off within a minute.",
        },
        {"objection_id": "O2", "action": "replace", "claim_id": "C3", "text": "Go-live: Jan 18."},
        {
            "objection_id": "C1",
            "action": "assume",
            "text": "Confirm with the client: their data-retention rule.",
        },
        {"objection_id": "X9", "action": "remove", "claim_id": "C1"},
    ]
}
REVOTE_ONE = [
    CFO
    | {
        "ratings": ratings(8, 8, 8),
        "objections": [],
        "previous": [{"id": "O1", "state": "resolved"}, {"id": "O3", "state": "resolved"}],
    },
    VP
    | {
        "ratings": ratings(9, 8, 8, seat="vp_director"),
        "objections": [],
        "previous": [{"id": "O2", "state": "partly"}],
    },
    ARCHITECT
    | {
        "ratings": ratings(9, 8, 8, seat="enterprise_architect"),
        "objections": [],
        "previous": [{"id": "O3", "state": "resolved"}],
    },
    ALL_MET_PROCUREMENT,
    {
        "items": [
            {"id": "data_protection", "status": "met"},
            {"id": "access_control", "status": "met"},
            {"id": "data_rules_fit", "status": "partly"},
        ],
        "previous": [{"id": "O7", "state": "resolved"}],
    },
]


@pytest.fixture
def round_one(scripted: Scripted) -> dict[str, Any]:
    base = state()
    return carry(base, review(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS], base))


def test_northwind_loop_fixes_only_what_the_raising_seat_resolves(
    scripted: Scripted, round_one: dict[str, Any]
) -> None:
    assert round_one["stop"]["stopped"] is False
    body = revise(
        scripted, round_one, 1, [reply_json(BID_ROUND_ONE)] + [reply_json(a) for a in REVOTE_ONE]
    )
    outcomes = [(c["objection_id"], c["outcome"]) for c in body["bid_round"]["changes"]]
    assert outcomes == [
        ("O1", "applied"),
        ("O3", "applied"),
        ("O2", "locked"),
        ("C1", "applied"),
        ("X9", "unknown_objection"),
    ]
    assert body["bid_round"]["answered"] == ["C1", "O1", "O3"]
    assert body["draft_no"] == 2
    texts = {c["id"]: c for c in body["claims"]}
    assert texts["C1"]["text"].startswith("Two phases") and texts["C3"]["text"].startswith(
        "Go-live: Mon"
    )
    assert texts["C6"]["origin"] == "assumption"
    status = {t["id"]: t["status"] for t in body["tracker"]}
    # O1 and O3 resolved by their raising seats; O4-O7 by the gates' re-reads; O2 only partly.
    assert status == {
        "O1": "fixed",
        "O2": "open",
        "O3": "fixed",
        "O4": "fixed",
        "O5": "fixed",
        "O6": "fixed",
        "O7": "fixed",
        "C1": "open",
    }
    assert body["round"]["no"] == 2 and body["round"]["progress"] == {"able": 5, "total": 5}
    assert body["stop"]["reasons"] == ["all_proceed"]
    assert body["verdict"]["label"] == "Approved with conditions"
    manager = body["steps"][0]
    assert (manager["agent"], manager["stage"], manager["badge"]) == ("bid_manager", 4, "fake-main")
    assert "Code refused 2 changes" in manager["summary"]


def test_seats_get_their_own_open_items_and_the_changes_in_a_revote(
    scripted: Scripted, round_one: dict[str, Any]
) -> None:
    revise(
        scripted, round_one, 1, [reply_json(BID_ROUND_ONE)] + [reply_json(a) for a in REVOTE_ONE]
    )
    cfo_request = scripted.model.requests[1]
    system, user = cfo_request.messages[0]["content"], cfo_request.messages[1]["content"]
    assert "your_open_items" in system and '"resolved", "partly" or "open"' in system
    assert '"your_open_items": [{"id": "O1"' in user
    assert '"changes_since_last_draft"' in user and "Two phases" in user
    assert '"id": "O2"' not in user.split('"proposal"')[0]  # the VP's item is not the CFO's


def test_the_report_after_the_loop_is_built_by_code(
    scripted: Scripted, round_one: dict[str, Any]
) -> None:
    body = revise(
        scripted, round_one, 1, [reply_json(BID_ROUND_ONE)] + [reply_json(a) for a in REVOTE_ONE]
    )
    final = report_of(after_revision(round_one, body))
    assert (final["verdict"], final["verdict_code"]) == (
        "Approved with conditions",
        "approved_with_conditions",
    )
    # Round 1 average: (5.3 + 7.1 + 6.2) / 3 = 6.2; round 2: (8.0 + 8.4 + 8.4) / 3 = 8.27
    assert final["headline"] == "Draft 1 scored 6.2. After 1 revision round it scored 8.3."
    numbers = {n["label"]: n for n in final["numbers"]}
    assert numbers["Average score, scoring seats"]["value"] == "6.2 → 8.3"
    assert (numbers["Objections fixed"]["value"], numbers["Objections fixed"]["note"]) == (
        "6 of 7",
        "+1 condition to confirm",
    )
    assert final["confirm_with_client"] == ["Retention rule unknown"]
    assert final["summary"].startswith(
        "5 of 5 board seats can proceed. Confirm 1 thing with Northwind Insurance"
    )
    assert [(c["objection_id"], c["action"]) for c in final["changes"]] == [
        ("O1", "Changed"),
        ("O3", "Added"),
        ("C1", "Assumption"),
    ]
    assert [m["decision"] for m in final["memo"]] == [
        "Approved",
        "Yes, with a condition",
        "Approved",
        "Pass",
        "Pass, with conditions",
    ]
    assert final["stop"]["reasons"] == ["all_proceed"]


def test_no_round_after_the_loop_stopped(scripted: Scripted, round_one: dict[str, Any]) -> None:
    body = revise(
        scripted, round_one, 1, [reply_json(BID_ROUND_ONE)] + [reply_json(a) for a in REVOTE_ONE]
    )
    model = scripted.load([])
    again = client.post(
        "/api/revise", json={"state": after_revision(round_one, body), "round_no": 2}
    ).json()
    assert again["error"] == "input_blocked" and model.requests == []


# --- Stop rules through the stage, and never more than 3 board votes ---


def harbor_round_one(scripted: Scripted) -> dict[str, Any]:
    base = state(HARBOR_FLAGS)
    return carry(
        base, review(scripted, [reply_json(CFO), reply_json(VP), reply_json(PROCUREMENT)], base)
    )


def harbor_revote(cfo_rating: float) -> list[FakeStep]:
    bid = {
        "changes": [
            {
                "objection_id": "O1",
                "action": "replace",
                "claim_id": "C1",
                "text": "A smaller first step.",
            }
        ]
    }
    cfo = CFO | {
        "ratings": ratings(cfo_rating, cfo_rating, cfo_rating),
        "objections": [],
        "previous": [{"id": "O1", "state": "partly"}],
    }
    return [
        reply_json(bid),
        reply_json(cfo),
        reply_json(VP | {"objections": []}),
        reply_json(PROCUREMENT | {"objections": []}),
    ]


def test_never_more_than_three_board_votes(scripted: Scripted) -> None:
    current = harbor_round_one(scripted)  # CFO 5.3 and VP 7.1: average 6.2
    first = revise(scripted, current, 1, harbor_revote(6.0))  # average 6.55: gain 0.35
    assert first["stop"]["stopped"] is False
    current = after_revision(current, first)
    second = revise(scripted, current, 2, harbor_revote(6.5))  # average 6.8: gain 0.25
    assert second["stop"]["reasons"] == ["max_rounds"] and second["round"]["no"] == 3
    current = after_revision(current, second)
    model = scripted.load([])
    third = client.post("/api/revise", json={"state": current, "round_no": 3}).json()
    assert third["error"] == "input_blocked" and model.requests == []
    assert len(current["rounds"]) == 3
    assert (
        report_of(current)["headline"]
        == "Draft 1 scored 6.2. After 2 revision rounds it scored 6.8."
    )


def test_a_round_that_improves_nothing_stops_the_loop(scripted: Scripted) -> None:
    current = harbor_round_one(scripted)
    body = revise(scripted, current, 1, harbor_revote(5.3))
    assert body["stop"]["reasons"] == ["no_gain"]
    assert "improved nothing" in body["stop"]["lines"][0]


def test_lite_mode_runs_one_bid_round(scripted: Scripted) -> None:
    current = harbor_round_one(scripted) | {"mode": "lite"}
    body = revise(scripted, current, 1, harbor_revote(6.5))
    assert "max_rounds" in body["stop"]["reasons"]


def test_the_cost_guard_stops_before_any_bid_round(scripted: Scripted) -> None:
    expensive = state() | {
        "steps": [
            {
                "agent": "business_analyst",
                "label": "Business Analyst",
                "tier": "haiku",
                "model": "m",
                "stage": 1,
                "start_ms": 0,
                "duration_ms": 1,
                "cost_usd": 0.3,
            }
        ]
    }
    board = review(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS], expensive)
    assert "guard" in board["stop"]["reasons"]
    model = scripted.load([])
    body = client.post("/api/revise", json={"state": carry(expensive, board), "round_no": 1}).json()
    assert body["error"] == "input_blocked" and model.requests == []


def test_a_round_number_out_of_order_is_refused(
    scripted: Scripted, round_one: dict[str, Any]
) -> None:
    model = scripted.load([])
    body = client.post("/api/revise", json={"state": round_one, "round_no": 2}).json()
    assert body["error"] == "input_blocked" and model.requests == []


def test_a_failed_bid_manager_fails_the_stage_and_keeps_the_board(
    scripted: Scripted, round_one: dict[str, Any]
) -> None:
    body = revise(scripted, round_one, 1, [reply_text("nope")] * 4)
    assert body["error"] == "step_failed"


# --- Appendix B failure tests F1 to F4 ---


def passing(seat: dict[str, Any], seat_id: str) -> dict[str, Any]:
    return seat | {"ratings": ratings(9, 9, 9, seat=seat_id), "objections": []}


PASSING_SCORERS = [
    passing(CFO, "cfo"),
    passing(VP, "vp_director"),
    passing(ARCHITECT, "enterprise_architect"),
]


def board_and_report(
    scripted: Scripted, script: list[FakeStep], flags: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = state(flags) if flags else state()
    board = review(scripted, script, base)
    return board, report_of(carry(base, board))


def test_f1_a_rejection_wins_over_a_failed_seat(scripted: Scripted) -> None:
    script = [
        reply_json(CFO),
        reply_json(passing(VP, "vp_director")),
        fail("server"),
        fail("server"),
        fail("server"),
        reply_json(ALL_MET_PROCUREMENT),
        reply_json(
            passing({"items": []}, "cfo")
            | {
                "items": [
                    {"id": i, "status": "met"}
                    for i in ("data_protection", "access_control", "data_rules_fit")
                ]
            }
        ),
    ]
    board, final = board_and_report(scripted, script)
    architect = next(s for s in board["round"]["seats"] if s["seat_id"] == "enterprise_architect")
    assert architect["status"] == "not_reviewed"
    assert final["verdict"] == "Not ready yet"


def test_f2_a_failed_gate_gives_review_incomplete_never_approved(scripted: Scripted) -> None:
    script = (
        [reply_json(s) for s in PASSING_SCORERS]
        + [reply_json(ALL_MET_PROCUREMENT)]
        + [fail("server")] * 3
    )
    _, final = board_and_report(scripted, script)
    assert final["verdict"] == "Review incomplete"


def test_f3_a_blocked_gate_caps_the_verdict(scripted: Scripted) -> None:
    blocked = {
        "items": [
            {"id": "data_protection", "status": "met"},
            {"id": "access_control", "status": "not_met"},
            {"id": "data_rules_fit", "status": "met"},
        ]
    }
    script = [reply_json(s) for s in PASSING_SCORERS] + [
        reply_json(ALL_MET_PROCUREMENT),
        reply_json(blocked),
    ]
    _, final = board_and_report(scripted, script)
    assert final["verdict"] == "Not ready yet"
    memo = {m["seat_id"]: m for m in final["memo"]}
    assert memo["security"]["decision"] == "Blocked"
    assert "Access control: not met" in memo["security"]["reason"]


def test_f4_a_seat_that_was_not_selected_never_counts(scripted: Scripted) -> None:
    script = [
        reply_json(passing(CFO, "cfo")),
        reply_json(passing(VP, "vp_director")),
        reply_json(ALL_MET_PROCUREMENT),
    ]
    board, final = board_and_report(scripted, script, HARBOR_FLAGS)
    assert [s["seat_id"] for s in board["round"]["seats"]] == ["cfo", "vp_director", "procurement"]
    assert final["verdict"] == "Approved"


def test_a_forced_not_ready_yet(scripted: Scripted) -> None:
    _, final = board_and_report(scripted, [reply_json(a) for a in NORTHWIND_ANSWERS])
    assert final["verdict"] == "Not ready yet"
    assert final["headline"] == "Draft 1 scored 6.2. No revision round was run."


def test_after_a_retry_the_verdict_is_computed_again(scripted: Scripted) -> None:
    script = (
        [reply_json(s) for s in PASSING_SCORERS]
        + [reply_json(ALL_MET_PROCUREMENT)]
        + [fail("server")] * 3
    )
    base = state()
    board = review(scripted, script, base)
    current = carry(base, board)
    assert report_of(current)["verdict"] == "Review incomplete"
    met = {
        "items": [
            {"id": i, "status": "met"}
            for i in ("data_protection", "access_control", "data_rules_fit")
        ]
    }
    scripted.load([reply_json(met)])
    retried = client.post("/api/board/retry", json={"state": current, "seat_id": "security"}).json()
    current = current | {"rounds": [retried["round"]], "tracker": retried["tracker"]}
    assert retried["verdict"]["label"] == "Approved"
    assert report_of(current)["verdict"] == "Approved"
