"""The final report (plan sections 7.2 and 8), built by code from the run state.

Every number here comes from code: the seats' scores, the tracker, the cost calculator and the
working-day schedule. The verdict follows section 4.7.
"""

from domain.claims import format_date, format_money, normalize_text
from domain.loop import average_score, final_verdict
from domain.tracker import checklist_text
from schemas.board import BoardRound, SeatResult
from schemas.revision import KeyNumber, MemoRow, Report, ReportChange, StopDecision
from schemas.state import RunState, TrackerItem

TO_CONFIRM = "To confirm"
ACTION_WORDS = {"replace": "Changed", "remove": "Removed", "add": "Added", "assume": "Assumption"}
NO_STOP = StopDecision(stopped=False, reasons=[], lines=[])

NOT_ANSWERED = "Not answered by the Bid Manager"


def score_text(score: float | None) -> str:
    return "—" if score is None else f"{score:.1f}"


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def headline(rounds: list[BoardRound], revisions: int) -> str:
    first, last = average_score(rounds[0]), average_score(rounds[-1])
    if revisions == 0:
        return f"Draft 1 scored {score_text(first)}. No revision round was run."
    return (
        f"Draft 1 scored {score_text(first)}. After {plural(revisions, 'revision round')} "
        f"it scored {score_text(last)}."
    )


def open_conditions(tracker: list[TrackerItem]) -> list[str]:
    """Items only the client can confirm, still open: they go to the meeting, each once."""
    texts: dict[str, str] = {}
    for item in tracker:
        if item.kind == "C" and item.status == "open":
            texts.setdefault(normalize_text(item.text), item.text)
    return list(texts.values())


def summary(latest: BoardRound, client: str, confirm: list[str]) -> str:
    seats = f"{latest.progress.able} of {latest.progress.total} board seats can proceed."
    if not confirm:
        return seats
    return f"{seats} Confirm {plural(len(confirm), 'thing')} with {client} before the meeting."


def score_number(rounds: list[BoardRound]) -> KeyNumber:
    first, last = average_score(rounds[0]), average_score(rounds[-1])
    titles = [s.title for s in rounds[-1].seats if s.kind == "scoring"]
    value = score_text(first) if len(rounds) == 1 else f"{score_text(first)} → {score_text(last)}"
    return KeyNumber(label="Average score, scoring seats", value=value, note=", ".join(titles))


def fixed_number(tracker: list[TrackerItem]) -> KeyNumber:
    objections = [t for t in tracker if t.kind == "O"]
    fixed = sum(t.status == "fixed" for t in objections)
    confirm = len(open_conditions(tracker))
    note = f"+{plural(confirm, 'condition')} to confirm" if confirm else ""
    return KeyNumber(label="Objections fixed", value=f"{fixed} of {len(objections)}", note=note)


def cost_number(state: RunState) -> KeyNumber:
    estimate = state.estimate
    if estimate is None or not estimate.phases:
        return KeyNumber(label="Phase 1 cost", value=TO_CONFIRM, note="No day rate is stated")
    phase_one = format_money(estimate.phases[0].cost, estimate.currency)
    note = f"Total {format_money(estimate.total, estimate.currency)}"
    return KeyNumber(label="Phase 1 cost", value=phase_one, note=note)


def go_live_number(state: RunState) -> KeyNumber:
    schedule = state.schedule
    if schedule is None:
        return KeyNumber(label="Go-live", value=TO_CONFIRM, note="The start date is to confirm")
    note = (
        "After public holidays"
        if schedule.holidays_checked
        else "Weekends skipped; public holidays not checked yet"
    )
    return KeyNumber(label="Go-live", value=format_date(schedule.go_live), note=note)


def report_changes(state: RunState) -> list[ReportChange]:
    rows = []
    for bid_round in state.revisions:
        for change in bid_round.changes:
            if change.outcome != "applied":
                continue
            text = change.new_text or f"Removed: {change.old_text or ''}".strip()
            rows.append(
                ReportChange(
                    objection_id=change.objection_id,
                    round=bid_round.no,
                    action=ACTION_WORDS[change.action],
                    text=text,
                )
            )
    return rows


def seat_reason(seat: SeatResult, tracker: list[TrackerItem]) -> str:
    """One line per seat for the memo, picked by code from the seat's own words."""
    if seat.status == "not_reviewed":
        return "Did not answer, so this seat is not reviewed. Retry the seat."
    open_texts = [t.text for t in tracker if t.seat == seat.seat_id and t.status == "open"]
    if seat.kind == "gate":
        gaps = [checklist_text(i) for i in seat.items if i.status not in ("met", "missing")]
        return " ".join(gaps) if gaps else "Every checklist item is met."
    if seat.condition:
        return seat.condition
    if open_texts:
        return open_texts[0]
    rated = [c for c in seat.criteria if c.rating is not None and c.reason]
    return min(rated, key=lambda c: c.rating or 0.0).reason if rated else ""


def memo(latest: BoardRound, tracker: list[TrackerItem]) -> list[MemoRow]:
    return [
        MemoRow(
            seat_id=s.seat_id,
            title=s.title,
            decision=s.decision,
            vote=s.vote,
            outcome=s.outcome,
            score=s.score,
            needed=s.needed,
            reason=seat_reason(s, tracker),
        )
        for s in latest.seats
    ]


def not_answered(state: RunState) -> list[ReportChange]:
    """Objections the Bid Manager left out in a round and that are still open, each once with
    the last round that left it out."""
    still_open = {t.id: t for t in state.tracker if t.status == "open"}
    rows: dict[str, ReportChange] = {}
    for bid_round in state.revisions:
        for item_id in bid_round.not_answered:
            if item_id in still_open:
                text = still_open[item_id].text
                rows[item_id] = ReportChange(
                    objection_id=item_id, round=bid_round.no, action=NOT_ANSWERED, text=text
                )
    return list(rows.values())


def build_report(state: RunState) -> Report:
    rounds, tracker = state.rounds, state.tracker
    latest = rounds[-1]
    verdict = final_verdict(latest, tracker)
    confirm = open_conditions(tracker)
    client = state.case_file.client if state.case_file else "the client"
    return Report(
        verdict_code=verdict.code,
        verdict=verdict.label,
        headline=headline(rounds, len(state.revisions)),
        summary=summary(latest, client, confirm),
        numbers=[
            score_number(rounds),
            fixed_number(tracker),
            cost_number(state),
            go_live_number(state),
        ],
        changes=report_changes(state),
        memo=memo(latest, tracker),
        confirm_with_client=confirm,
        stop=state.stop or NO_STOP,
        not_answered=not_answered(state),
    )
