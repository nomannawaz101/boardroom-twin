"""Choose the board for one brief from the Business Analyst's flags (plan section 4.2).

Pure code. An unclear flag (null) always makes the seat join: a missing review is worse than an
extra one. Every seat carries a one-line reason written by code from fixed text.
"""

from domain.seats import SEATS, SEATS_BY_ID, SeatSpec
from schemas.board import BoardPlan, PlannedSeat, SkippedSeat
from schemas.case_file import BoardFlags

MIN_SEATS = 3
MAX_SEATS = 5
FILLER_SEAT = "enterprise_architect"
UNCLEAR_FUNCTION = "Operations"
LARGE_PREFIX = "VP"
SMALL_PREFIX = "Director"

ALWAYS_WHY = {
    "cfo": "Always on the board: owns the budget.",
    "vp_director": "Always on the board: owns the business outcome.",
}
EXISTING_SYSTEMS_WHY = {
    True: "Existing systems are touched.",
    None: "Unclear whether existing systems are touched.",
}
NO_EXISTING_SYSTEMS = "No existing system is touched."
CONTRACT_WHY = {
    "fixed": "Fixed-price contract.",
    "tm": "Time-and-materials contract.",
    "other": "Vendor contract.",
    None: "Contract type unclear.",
}
NO_CONTRACT = "No vendor contract."
PERSONAL_DATA_WHY = {
    True: "Personal data is involved.",
    None: "Unclear whether personal data is involved.",
}
NO_PERSONAL_DATA = "No personal data is involved."
FILLER_WHY = "Added so the board has at least 3 seats."


def vp_title(flags: BoardFlags) -> str:
    prefix = SMALL_PREFIX if flags.seniority == "small" else LARGE_PREFIX
    function = (flags.function or "").strip() or UNCLEAR_FUNCTION
    return f"{prefix}, {function}"


def join_reason(seat: SeatSpec, flags: BoardFlags) -> tuple[bool, str]:
    """Return (joins, reason) for one seat."""
    if seat.join_rule == "always":
        return True, ALWAYS_WHY[seat.id]
    if seat.join_rule == "existing_systems":
        joins = flags.existing_systems is not False
        return joins, EXISTING_SYSTEMS_WHY[flags.existing_systems] if joins else NO_EXISTING_SYSTEMS
    if seat.join_rule == "contract":
        joins = flags.contract_type != "none"
        return joins, CONTRACT_WHY[flags.contract_type] if joins else NO_CONTRACT
    joins = flags.personal_data is not False
    return joins, PERSONAL_DATA_WHY[flags.personal_data] if joins else NO_PERSONAL_DATA


def seat_title(seat: SeatSpec, flags: BoardFlags) -> str:
    return vp_title(flags) if seat.id == "vp_director" else seat.title


def compose_board(flags: BoardFlags) -> BoardPlan:
    chosen: list[PlannedSeat] = []
    skipped: list[SkippedSeat] = []
    for seat in SEATS:
        joins, reason = join_reason(seat, flags)
        title = seat_title(seat, flags)
        if joins:
            chosen.append(PlannedSeat(id=seat.id, kind=seat.kind, title=title, why=reason))
        else:
            skipped.append(SkippedSeat(id=seat.id, title=title, why_not=reason))
    if len(chosen) < MIN_SEATS:
        chosen, skipped = add_filler(chosen, skipped)
    return BoardPlan(seats=chosen[:MAX_SEATS], skipped=skipped)


def add_filler(
    chosen: list[PlannedSeat], skipped: list[SkippedSeat]
) -> tuple[list[PlannedSeat], list[SkippedSeat]]:
    """Rule 5: below 3 seats, the Enterprise Architect joins. Registry order is kept."""
    spec = SEATS_BY_ID[FILLER_SEAT]
    filler = PlannedSeat(id=spec.id, kind=spec.kind, title=spec.title, why=FILLER_WHY)
    order = [s.id for s in SEATS]
    seats = sorted([*chosen, filler], key=lambda s: order.index(s.id))
    return seats, [s for s in skipped if s.id != FILLER_SEAT]
