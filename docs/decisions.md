# Decisions

A short record of each choice, including ones still unconfirmed.

## Phase 0

- **Nested-import proof:** `routers/health.py` imports `domain/status.py` (a small pure function that builds the health summary), so the first deploy proves nested packages import on Vercel.
- **Working days tool built early:** `tools/working_days.py` (pure code, tested) is needed by `scripts/check_llm.py` for the tool round trip, so it lands in Phase 0 instead of Phase 1.
- **Secret scan private terms:** names that must never appear in the repo cannot be written into the scanner, so it reads them from `SECRET_SCAN_TERMS` in `.env.local` (laptop only). It also treats every `.env.local` value as a secret, and fails if `PLAN.md` or an env file is tracked. Findings name the file and rule, never the matched value.
- **Pre-commit hook:** a plain git hook in `.git/hooks/pre-commit`; no extra library.
- **pytest settings:** `pytest.ini` (not `pyproject.toml`, which Vercel's Python builder may read).
- **Git flow:** first commit (`.gitignore`) on `main`; after that one branch per phase (`phase-N-name`), merged by pull request. `main` is never pushed to directly. Vercel builds previews from branches and production from `main`.
- **Placeholders:** `MAX_OUT_DEFAULT = 2500` until measured (plan section 9.2). `CHECK_MAX_TOKENS = 1024` for the gateway check.
