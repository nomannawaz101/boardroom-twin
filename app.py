"""Thin entry point: creates the app, includes the routers and serves the static page."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from domain.errors import AppError, InputBlocked, StepFailed
from routers import board, discover, draft, health, version

STATIC_DIR = config.PROJECT_ROOT / "static"
BAD_SHAPE = "The request was not in the expected shape. Please start again from the brief."

log = logging.getLogger("boardroom")

app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION)
for module in (health, version, discover, draft, board):
    app.include_router(module.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def error_response(error: AppError) -> JSONResponse:
    """The only error shape a user ever sees: a fixed code and a friendly line (guard G11)."""
    return JSONResponse({"error": error.code, "message": error.message}, status_code=error.status)


@app.exception_handler(AppError)
async def app_error(request: Request, error: AppError) -> JSONResponse:
    return error_response(error)


@app.exception_handler(RequestValidationError)
async def bad_shape(request: Request, error: RequestValidationError) -> JSONResponse:
    return error_response(InputBlocked(BAD_SHAPE))


@app.middleware("http")
async def catch_all(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Catch-all: an unexpected error becomes step_failed. A middleware, not an exception
    handler, because Starlette re-raises after its handler and the traceback would be logged.
    """
    try:
        return await call_next(request)
    except Exception as error:  # noqa: BLE001 - every unexpected error gets the same safe reply
        # Only the type name is logged: exception text can hold addresses or brief content.
        log.error("unexpected error type=%s path=%s", type(error).__name__, request.url.path)
        return error_response(StepFailed())


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
