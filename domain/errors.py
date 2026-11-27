"""Typed errors with the codes of plan section 7.1. The message is the only text a user sees."""


class AppError(Exception):
    code = "step_failed"
    status = 200
    message = "Something went wrong in this step. Please retry."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class StepFailed(AppError):
    code = "step_failed"


class RateLimited(AppError):
    code = "rate_limited"
    message = "The model service is busy. Please retry in a moment."


class BudgetUsedUp(AppError):
    code = "budget_used_up"
    message = "The live budget is used up. The sample run is still available."


class BadPasscode(AppError):
    code = "bad_passcode"
    status = 403
    message = "That passcode is not right. The sample run is free to watch."


class NotABrief(AppError):
    code = "not_a_brief"
    message = "This does not look like a client brief."


class InputBlocked(AppError):
    code = "input_blocked"
    status = 422


class TooLong(AppError):
    code = "too_long"
    status = 422


class UploadRefused(AppError):
    code = "upload_refused"
    status = 422


class GateNotReviewed(AppError):
    code = "gate_not_reviewed"
    message = "A board seat could not review the proposal. Retry that seat."
