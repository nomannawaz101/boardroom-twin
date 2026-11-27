"""Thin entry point: creates the app, includes the routers and serves the static page."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from routers import health, version

STATIC_DIR = config.PROJECT_ROOT / "static"

app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION)
app.include_router(health.router)
app.include_router(version.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
