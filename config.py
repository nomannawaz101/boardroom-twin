"""Settings, switches and limits. Every tunable number lives here, not in the code that uses it."""

import os
from pathlib import Path
from typing import Literal, get_args

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

# Tests set this so they never read the laptop's real settings file.
SKIP_ENV_FILE_VAR = "BOARDROOM_SKIP_ENV_FILE"

# Only the laptop has this file; on Vercel the values come from project environment variables.
if not os.getenv(SKIP_ENV_FILE_VAR):
    load_dotenv(PROJECT_ROOT / ".env.local")

APP_NAME = "Boardroom Twin"
APP_VERSION = "0.2.0"

RunMode = Literal["auto", "full", "lite", "sample"]
DEFAULT_RUN_MODE: RunMode = "auto"

# Extras are switched on in later phases (plan section 3); all off until built.
# `risk_analyst` is core, not an extra: it stays off only until Phase 5 builds it, so handoff
# lines never name an agent that did not run.
FEATURES: dict[str, bool] = {
    "risk_analyst": False,
    "qa_reviewer": False,
    "run_details": False,
    "upload": False,
    "meeting_prep": False,
    "prototype": False,
}

# Vercel sets this to the deployed commit; it is absent on the laptop.
COMMIT_ENV_VAR = "VERCEL_GIT_COMMIT_SHA"
UNKNOWN_COMMIT = "local"

# --- Model gateway. Only names live here; values come from .env.local or Vercel. ---
LLM_BASE_URL_VAR = "LITELLM_BASE_URL"
LLM_API_KEY_VAR = "LITELLM_API_KEY"
LLM_MODEL_VAR = "LITELLM_MODEL"
LLM_MODEL_FAST_VAR = "LITELLM_MODEL_FAST"
LLM_TIMEOUT_S = 60.0
UNSET_MODEL = "unset"

# scripts/check_llm.py: small answers keep the check to a few cents. Some models count hidden
# reasoning toward this cap, so it is set above the visible answer size.
CHECK_MAX_TOKENS = 1024

# --- Model routing (plan section 3): one table. Lite mode sends every agent to the fast tier. ---
Tier = Literal["sonnet", "haiku"]
FAST_TIER: Tier = "haiku"
TIER_MODEL_VARS: dict[Tier, str] = {"sonnet": LLM_MODEL_VAR, "haiku": LLM_MODEL_FAST_VAR}
MODEL_ROUTING: dict[str, Tier] = {
    "business_analyst": "haiku",
    "solution_architect": "sonnet",
    "delivery_manager": "sonnet",
    "risk_analyst": "sonnet",
    "proposal_manager": "sonnet",
    "bid_manager": "sonnet",
    "qa_reviewer": "haiku",
    "presales_lead": "haiku",
    "ux_designer": "sonnet",
    "cfo": "sonnet",
    "vp_director": "sonnet",
    "enterprise_architect": "sonnet",
    "procurement": "haiku",
    "security": "haiku",
}

# --- Answer caps (plan section 9.2). Placeholders until measured in Phases 6 and 10. ---
MAX_OUT_DEFAULT = 2500
MAX_OUT: dict[str, int] = {}
TRUNCATION_CAP_FACTOR = 2  # a cut-off answer is retried once with this many times the cap

# --- Retries (plan section 10). ---
JSON_RETRIES = 3  # invalid JSON is retried this many times, then a safe default marked skipped
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BASE_WAIT_S = 2.0  # doubles on each retry
MODEL_ERROR_RETRIES = 1  # on the routed model, before one last try on the fast model
MODEL_ERROR_BASE_WAIT_S = 1.0
MAX_TOOL_ROUNDS = 5

# --- Prices in USD per million tokens (plan section 9.1, published 27 Nov 2026). Placeholders:
# the gateway's own spend figure is the truth. ---
PRICE_PER_MTOK: dict[Tier, tuple[float, float]] = {"sonnet": (2.0, 10.0), "haiku": (0.10, 0.50)}
TOKENS_PER_MTOK = 1_000_000
COST_DECIMALS = 6
MONEY_DECIMALS = 2

# --- Tools (plan section 5). ---
OUTSIDE_CALL_TIMEOUT_S = 5.0
WORKING_DAYS_PER_WEEK = 5

# --- Input limits (plan section 6.1, guard G2). ---
BRIEF_MAX_CHARS = 15_000
CLIENT_NAME_MAX_CHARS = 80
MAX_BLANK_LINES = 2
# Fixed country list for the form; the ISO code feeds the public-holidays tool in Phase 5.
COUNTRIES: dict[str, str] = {
    "Australia": "AU",
    "Austria": "AT",
    "Belgium": "BE",
    "Canada": "CA",
    "Denmark": "DK",
    "France": "FR",
    "Germany": "DE",
    "Ireland": "IE",
    "Italy": "IT",
    "Netherlands": "NL",
    "Pakistan": "PK",
    "Poland": "PL",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "United Arab Emirates": "AE",
    "United Kingdom": "GB",
    "United States": "US",
}

# --- Real-data guard (plan section 6.1, G6). ---
CARD_MIN_DIGITS = 13
CARD_MAX_DIGITS = 19
PHONE_MIN_DIGITS = 9
PHONE_MAX_DIGITS = 15
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "lumenworks.example")
SAFE_EMAIL_SUFFIXES = (".test", ".invalid", ".example")

# --- List caps on model answers (plan section 7.2: every list is length-capped). ---
LIST_CAP_SHORT = 6
LIST_CAP_MEDIUM = 12
LIST_CAP_LONG = 40

CURRENCY_SYMBOLS: dict[str, str] = {"USD": "$", "EUR": "€", "GBP": "£"}
DEFAULT_CURRENCY = "USD"

# --- Proposal drafting (plan sections 7.2 and 8). ---
PROPOSAL_SECTION_COUNT = 9
CLAIM_MAX_WORDS = 20
PM_TARGET_CLAIMS = (12, 24)  # asked of the Proposal Manager; code caps the list at LIST_CAP_LONG


def run_mode() -> RunMode:
    """Read RUN_MODE; an unknown value falls back to the default instead of failing the app."""
    value = os.getenv("RUN_MODE", DEFAULT_RUN_MODE).strip().lower()
    return value if value in get_args(RunMode) else DEFAULT_RUN_MODE


def deployed_commit() -> str:
    return os.getenv(COMMIT_ENV_VAR) or UNKNOWN_COMMIT


def model_for_tier(tier: Tier) -> str:
    return os.getenv(TIER_MODEL_VARS[tier]) or UNSET_MODEL


def max_out(agent_id: str) -> int:
    return MAX_OUT.get(agent_id, MAX_OUT_DEFAULT)
