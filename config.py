"""Settings, switches and limits. Every tunable number lives here, not in the code that uses it."""

import os
from pathlib import Path
from typing import Literal, get_args

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

# Only the laptop has this file; on Vercel the values come from project environment variables.
load_dotenv(PROJECT_ROOT / ".env.local")

APP_NAME = "Boardroom Twin"
APP_VERSION = "0.1.0"

RunMode = Literal["auto", "full", "lite", "sample"]
DEFAULT_RUN_MODE: RunMode = "auto"

# Extras are switched on in later phases (plan section 3); all off until built.
FEATURES: dict[str, bool] = {
    "qa_reviewer": False,
    "run_details": False,
    "upload": False,
    "meeting_prep": False,
    "prototype": False,
}

# Vercel sets this to the deployed commit; it is absent on the laptop.
COMMIT_ENV_VAR = "VERCEL_GIT_COMMIT_SHA"
UNKNOWN_COMMIT = "local"

# Output ceiling for every agent until real usage is measured (plan section 9.2).
MAX_OUT_DEFAULT = 2500

# Outside calls (public APIs) give up after this many seconds (plan section 5).
OUTSIDE_CALL_TIMEOUT_S = 5.0

# Model gateway. Only names live here; values come from .env.local or Vercel.
LLM_BASE_URL_VAR = "LITELLM_BASE_URL"
LLM_API_KEY_VAR = "LITELLM_API_KEY"
LLM_MODEL_VAR = "LITELLM_MODEL"
LLM_MODEL_FAST_VAR = "LITELLM_MODEL_FAST"
LLM_TIMEOUT_S = 60.0

# scripts/check_llm.py: small answers keep the check to a few cents. Some models count hidden
# reasoning toward this cap, so it is set above the visible answer size.
CHECK_MAX_TOKENS = 1024


def run_mode() -> RunMode:
    """Read RUN_MODE; an unknown value falls back to the default instead of failing the app."""
    value = os.getenv("RUN_MODE", DEFAULT_RUN_MODE).strip().lower()
    return value if value in get_args(RunMode) else DEFAULT_RUN_MODE


def deployed_commit() -> str:
    return os.getenv(COMMIT_ENV_VAR) or UNKNOWN_COMMIT
