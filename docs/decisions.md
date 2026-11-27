# Decisions

A short record of each choice, including ones still unconfirmed.

## Phase 0

- **Nested-import proof:** `routers/health.py` imports `domain/status.py` (a small pure function that builds the health summary), so the first deploy proves nested packages import on Vercel.
- **Working days tool built early:** `tools/working_days.py` (pure code, tested) is needed by `scripts/check_llm.py` for the tool round trip, so it lands in Phase 0 instead of Phase 1.
- **Secret scan private terms:** names that must never appear in the repo cannot be written into the scanner, so it reads them from `SECRET_SCAN_TERMS` in `.env.local` (laptop only). It also treats every `.env.local` value as a secret, and fails if `PLAN.md` or an env file is tracked. Findings name the file and rule, never the matched value.
- **Pre-commit hook:** a plain git hook in `.git/hooks/pre-commit`; no extra library.
- **pytest settings:** `pytest.ini` (not `pyproject.toml`, which Vercel's Python builder may read).
- **Git flow:** first commit (`.gitignore`) on `main`; after that one branch per phase (`phase-N-name`). Only the owner pushes, opens pull requests and merges; development commits stay local until reviewed. Vercel builds previews from branches and production from `main`.
- **Placeholders:** `MAX_OUT_DEFAULT = 2500` until measured (plan section 9.2). `CHECK_MAX_TOKENS = 1024` for the gateway check.

## Phase 1

- **New files inside existing folders** (no folder added): `domain/errors.py` (typed errors with the codes of section 7.1, shared by guards, llm and later routers), `llm/gateway.py` (the OpenAI-compatible adapter, kept apart so `run_agent` depends only on a small `ChatModel` interface that the fake also implements), `schemas/` split by contract (`step`, `claims`, `case_file`, `cost`, `answers`, `requests`, `state`, `common`).
- **run_agent signature:** `run_agent(agent_id, system, user, schema, tools=None, *, runtime, default=None)`. `runtime` carries the model, lite flag, tool context, clock and sleeper so tests stay free and instant. `default` is the safe answer used when JSON fails; a call that fails after every retry returns no answer with status `failed`.
- **Retry policy (all numbers in `config.py`):** invalid JSON retried 3 times then `skipped`; a cut-off answer retried once at twice the cap then `skipped`; 429 waits 2, 4, 8 s; other errors wait 1 s, retry, then one try on the fast tier (`fallback_fast`), then `failed`; budget or key errors raise `BudgetUsedUp` for Phase 6 to switch to Sample. Any retry sets the `retried` flag (also used for "busy, retrying").
- **JSON mode** is requested only when no tools are offered; with tools the answer is still extracted and checked.
- **Tools:** each tool checks its input with a pydantic model; bad input becomes `{"error": ...}` for the model, never a crash. A model can only call the tools offered to that agent. Results return inside `<tool_result>` tags. The quote checker reads the brief from code (`ToolContext`), not from the model. `check_llm.py` now uses the same tool runner.
- **Tool JSON schemas are written by hand**, not generated from pydantic, because generated schemas use `$ref` and `title`, which some providers reject.
- **Tests never read `.env.local`:** `tests/conftest.py` sets `BOARDROOM_SKIP_ENV_FILE` and fake model names before `config` is imported.
- **Lumen Works email domain:** G6 allows `lumenworks.example`, plus the `.example` suffix (reserved like `.test` and `.invalid`). Unconfirmed: change in `config.SAFE_EMAIL_DOMAINS` if the firm needs another address.
- **G6 patterns:** card numbers count only when contiguous or in 4-digit groups and passing Luhn, so dates and claim numbers never match; phones need a leading `+`, a leading `0`, or the North American 3-3-4 shape, with 9 to 15 digits. All three sample briefs pass; the hostile brief is stopped.
- **G9 limits:** numbers are compared as values (`$12,000` = `12000`). Spelled-out numbers ("two days") are not checked. Phase numbers and other code values are passed in as known numbers by the caller.
- **Claims:** a model cannot mark its own claim as calculated (it becomes `derived`); unknown origins become `derived`. Changes to locked claims and unknown claim ids are refused and reported, never applied.
- **Country list:** a fixed list of 18 countries with ISO codes in `config.COUNTRIES` (the code feeds the holidays tool in Phase 5). Unconfirmed: extend as needed.
- **Prices:** Sonnet $2 / $10 and Haiku $0.10 / $0.50 per million tokens (section 9.1), placeholders until the gateway's figures are known.
- **No invisible characters in source:** control, zero-width and bidi characters are written as code points (`chr(0x200B)`), never as literal characters, so reviewers can see everything in the code.
