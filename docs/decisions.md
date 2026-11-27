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

## Phase 2

- **Flow:** `/api/discover` runs guards G1 to G8, the Business Analyst and the board composer; `/api/draft` runs the Solution Architect, Delivery Manager and Proposal Manager in order. The Risk & Compliance Analyst is registered but switched off (`FEATURES["risk_analyst"]`) until Phase 5, so handoff lines never name an agent that did not run.
- **Only the Business Analyst reads the brief.** Later agents get the case file and quoted signals inside an `<inputs>` block (with `</` escaped so text cannot close the block). The brief returned by the browser is cleaned and checked again (G2, G3, G6) before stage 2.
- **Code decides what to trust:** a day rate is used only if the brief states that number; a start date only if the brief states its day and it is not in the past; effort comes from the Delivery Manager, renumbered by code, or else from the team the brief states. Missing rate or start becomes a TO CONFIRM assumption written by code.
- **Dates:** `domain/timeline.py` owns working-day maths (moved from `tools/`, which now imports it). Phases run back to back; go-live is start plus total working days. Public holidays join in Phase 5; until then a code-made assumption says so.
- **Calculated claims** now include the schedule (per-phase dates and go-live) as well as cost; all are locked and rebuilt by code.
- **Null lists from a model count as empty lists.** Seen live: a non-brief answered `"goals": null`, which failed validation, was retried four times and ended as `step_failed` instead of `not_a_brief`.
- **Errors:** typed errors return `{error, message}`; malformed requests return `input_blocked`; anything unexpected returns `step_failed` through a middleware (Starlette's own catch-all re-raises and would log the traceback). Only the error type is logged.
- **`callApi` change:** a typed server error is passed through with its message even on HTTP 422 (the plan's version turned every non-OK reply into `step_failed`, which would hide the exact limit for `too_long`).
- **`/api/health`** also returns `agents` and `tools`, counted from the registries, so the start panel can never overstate them.
- **Sample briefs** live once, in `static/sample/briefs.json`; tests read the same file. The Harbor Freight sample uses the client name "Harbor Freight Logistics" and the country United States (the brief states neither; unconfirmed).
- **Answer shapes are enforced on model replies.** `run_agent` validates each reply with the `FROM_MODEL` context, which turns on count and length rules: Solution Architect 2 to 5 parts and 1 to 3 phases; Delivery Manager at least 1 phase, each with at least 1 engineer and more than 0 weeks; Proposal Manager at least 10 claims of at most 20 words. Too few fails the check, is retried with the problem named (field path and rule only, never the reply's values; one reminder at a time), and after the retries ends as the safe default with the `skipped` flag. Too many is cut to the maximum, like every capped list. Code-built objects and the run state are not held to these rules, so a skipped default (for example a design with no parts) can still travel in the state. The ranges live in `config.py` and the prompts read them from there.
- **Proposal Manager target lowered from 12–24 to 10–24 claims:** live Gemini drafts held 9 to 14 claims, so a floor of 12 would have retried most runs. In the re-check, 2 of 3 drafts were retried once and then passed.
- **Email pattern bounded:** the local part is limited to 64 characters (the email standard's maximum). Unbounded, a 15,000-character brief with no spaces took 1.2 s to check because every position was rescanned.
- **Cost on the stage header is labelled "est."** with a tooltip: it is token counts at list prices (Claude prices applied to Gemini tokens during development), not a bill.
- **Accepted deviation (decided by the owner): Harbor Freight shows 4 seats on Gemini; re-check on Claude in Phase 10 and re-tune the Business Analyst prompt there if still wrong.** The composer applies section 4.2 exactly; Gemini's Business Analyst sometimes sets `existing_systems: true` for a support engineer on an existing platform, so the Enterprise Architect joins (one later run gave the expected 3 seats, so it varies). No flag is forced in code. Fake-model stage tests pin the rule: `existing_systems: false` gives exactly CFO, VP or Director, and Procurement & Contracts; null flags add the Enterprise Architect and Security Officer.
- **Rate limit on the free development key:** when the gate runs about 15 calls in 30 seconds, a following call can exhaust the 429 retries and end as `step_failed` after about 17 s; run alone, the same call answers in 2.5 s. Phase 6 adds the "busy, retrying" state for this. It does not affect the judged gateway's 60 requests a minute.

### Differences from the design (Phase 2)

- **Only four agents so far,** one after another: Business Analyst, Solution Architect, Delivery Manager, Proposal Manager. The Risk & Compliance Analyst and the "Ran at the same time" group arrive in Phase 5, with the currency converter and public holidays; the stage header says "Each agent hands its work to the next" instead of "Five agents … two work at the same time".
- **Upload and the sample run are switched off:** the upload block (Phase 8) and "Watch the sample run" (Phase 6) are shown disabled with a note saying they arrive in a later build. The passcode field is left out until Phase 6. "Next: send it to the client board" is disabled until Phase 3.
- **Start panel wording:** "Agent roles" shows the registry counts, "14, with 3 tools so far" (the design shows 5 tools); "Time" reads "About 2 to 3 minutes for a full run"; the brief card's subtitle reads "Paste text or pick a sample" (no upload yet).
- **Footer text:** "Lumen Works is a fictional firm. All client names and briefs are made up." and "Every number is decided by code, not by AI." instead of naming Northwind and linking to "What happens when something fails" (the failure states screen arrives in Phase 6).
- **Extra on the stage 2 screen:** the full tagged 9-section proposal is shown below the relay (the design shows it on the report screen), and the Business Analyst card also lists the board chosen by code.
