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

### Timeline without a start date (Phase 2 fix)

- **No section of a draft is ever empty.** Without a start date, code adds a calculated, locked timeline claim from the locked phase days: "Duration: 26 weeks (130 working days) from the start date. Start date to confirm.", and the existing TO CONFIRM assumption asks for the start date; the draft summary shows Start and Go-live as "To confirm". With a start date the per-phase dates and go-live stay as before. Part days round up exactly as the schedule does.
- **Without a day rate**, the cost section gets a calculated, locked effort claim ("Effort: 60 engineer-days over 1 phase. Cost to confirm: no day rate.") instead of being empty.
- **Any other empty section** (for example when the Proposal Manager skips one, or ends as the safe default) gets a code-written TO CONFIRM line: "Confirm with the client: next steps is not drafted yet." The page therefore no longer needs a "Nothing yet." state.
- All code-made wording lives in `domain/claims.py`; fake-model stage tests cover a draft with and without a start date, and one where the Proposal Manager is skipped, each checking all 9 sections are present.

### Where every number and label on the page comes from (Phase 2 honesty check)

| Shown | Where | Source |
| --- | --- | --- |
| Agent card seconds | agent cards | Measured: `duration_ms` from the run clock for that agent's calls |
| "· 1 tool" on a card | agent cards | Counted from the step's recorded tool calls |
| Model badge | agent cards | The model that answered, from the step record (after any fallback); "Sonnet"/"Haiku" only when the model belongs to that family, else the model's own name |
| "N agents" | stage header | Counted from the step records that ran |
| "N tool calls" | stage header | Counted from the step records' tool calls |
| "S s" | stage header | Measured: sum of the agents' `duration_ms` (agent time, not wall-clock time) |
| "$X est." | stage header | Measured tokens × the price table in `config.py` (list prices; during development Gemini tokens at Claude prices) — an estimate |
| Tokens | not shown yet | Measured from each reply's usage; on the step record, shown in Phase 7's run details |
| "14, with 3 tools so far" | start panel | Counted from the agent and tool registries via `/api/health` |
| Mode chip and "Sonnet and Haiku" | start panel, header | Mode from `RUN_MODE` (config); model names are the badges of the configured models via `/api/health` |
| "3 to 5 seats, chosen from your brief" | start panel | Fixed text matching the composer's rules (`MIN_SEATS`, `MAX_SEATS`) |
| "About 2 to 3 minutes for a full run" | start panel | Placeholder from plan section 10; replaced by measured runs in Phase 10 |
| "≈ $0.16 per run (estimate)" | start panel | Placeholder from plan section 9.1; replaced by measured runs in Phase 10 |
| "N / 15,000 characters" | brief form | Measured live; the limit is `BRIEF_MAX_CHARS`, kept equal to `config.py` by a test |
| Cost, team, start, go-live | draft summary | Calculated by code (cost calculator, working-day schedule) |

- **Model badge fix:** the badge used to print the configured tier ("Sonnet"/"Haiku") whatever model answered, so a development model was shown as Sonnet or Haiku. Now each reply's reported model is recorded (`model` on the step record, falling back to the requested model if the service does not say), and code derives `badge` from it. A fallback to the fast tier shows the fast model; with the judged gateway's models the tier names stay. The start panel's model line uses the same rule (`models` added to `/api/health`), and shows one name when both tiers use the same model.

## Phase 3

- **Seats are data, prompts are two templates.** `agents/board_seat.py` runs all five seats; `agents/prompts/scoring_seat.md` and `gate_seat.md` hold the Appendix A rules, and each seat's `lens` (what that buyer cares about) lives in its entry in `domain/seats.py`. This follows the plan's extension rule ("a new board seat is one data entry") instead of one prompt file per seat.
- **The seat title and client name travel as data.** The VP or Director title is built from the Business Analyst's `function` flag, which comes from the brief, so it is sent inside the `<inputs>` block, never in the system prompt.
- **Seats run only from `board_plan`, all at the same time** (`asyncio.gather`). Gate seats run on the fast tier, scoring seats on the main tier (`config.MODEL_ROUTING`).
- **Scores are exact.** Ratings are clamped to 0..10; the score is the weighted sum in decimal arithmetic, rounded half up to 2 decimals (so 6.995 meets a needed 7.0). A criterion the seat leaves out counts as 0 and marks the seat "partial". Criteria and checklist items are matched by id or label; the first answer for an item counts; unknown ones are ignored.
- **Decided by the owner — open blocker on a passing score:** a scoring seat whose score meets the needed score but still has an open **blocker** objection gives "Yes, with a condition", not Approved. Rule 2 names only conditions; approving with a blocker still open would be dishonest.
- **Decided by the owner — a gate answer that leaves a checklist item out:** a missing item is never counted as Met, Partly or Not met, because a Blocked must never come from a forgotten line instead of the model's own answer.
  1. The reply check (`check` on `run_agent`, `GateSeatAnswer.covers_the_checklist`) fails a reply that leaves an item out, naming the missing item, so the seat is retried like any other bad answer.
  2. After the retries, code uses the last reply that had the right shape (`AgentResult.unchecked`): if an item it answered is a **must-have Not met**, the gate is **Blocked** — a known result wins, marked partial, and the step record says `retried` with the `partial` flag.
  3. Otherwise the seat is **Not reviewed** with a "partial answer" flag and a Retry button: it cannot proceed and adds no tracker items until it answers in full. The answered items are still shown, and the missing one is shown as "Not answered".
  - Reading of "if any answered item is Not met, the gate is Blocked": only a must-have Not met can block (section 4.4 rule 3). A non-must Not met with an item missing stays undecided, so the seat is Not reviewed. Tested both ways.
- **Verdict (section 4.7), `domain/loop.py: final_verdict`, sent with every board response as "verdict so far":** any scoring seat Rejected or gate Blocked gives "Not ready yet" (a known result always wins over a failed call or a partial answer); otherwise any selected seat Not reviewed, partial or not, gives "Review incomplete"; otherwise anything still open, "Yes, with a condition" or "Pass, with conditions" gives "Approved with conditions"; otherwise "Approved". Phase 4 calls it after the last round.
- **Scoring seats keep rule 1 as written:** a criterion a scoring seat leaves out counts as 0 and marks the seat partial (section 4.4 rule 1 says so explicitly); only gate checklists use the retry-then-decide rule above.
- **Not reviewed.** Seats have no safe default: a seat whose call fails or whose answer cannot be used after the retries is Not reviewed, cannot proceed, and its step record has status `not_reviewed` with the flag. The other seats still count. If fewer than 2 seats answer, the stage fails with `step_failed` and the page offers Retry.
- **Retry this seat:** `POST /api/board/retry` with `{state, seat_id}` (not in the section 7.1 table). Only a seat that is Not reviewed in the latest round can be retried; its tracker items are appended with the next free ids, and the round's progress is recomputed from all seats.
- **Board response shape:** `{round: {no, seats, progress}, tracker, steps}`; the plan writes `{round: {seats, objections, progress}, steps}`. The objections are the tracker.
- **Tracker:** items carry the seat's `resolve_hint` (section 4.3 seat answers have it; section 4.5's shape does not), for the Bid Manager in Phase 4. Gate items that are Not met or Partly become items: blocker if a must-have is Not met, otherwise condition; the seat's own objection gives the wording, else code writes "Change control: not met.". Objections on met or unknown items are ignored; an unknown claim id is dropped from the item. Note: tracker ids C1, C2 share the letter C with claim ids (C7); this follows the plan, and the page always shows them in separate places.
- **Decision words** are written by code on each seat result: "Approved", "Yes, with a condition", "Rejected", "Pass", "Pass, with conditions" (the design's wording; the plan writes "Pass with conditions"), "Blocked", "Not reviewed".
- **Screen tests without a new library:** `tests/js/board_screen.test.mjs` renders the board cards with Node against a tiny DOM stand-in (not reviewed with Retry, score bar and tick, gate MUST marks, objections log, header stats); `tests/unit/test_board_screen.py` runs it and skips if Node is not installed.

### Differences from the design (Phase 3)

- **Why lines** on the board strip are the composer's fixed texts per rule (plan 4.2 rule 7, for example "Existing systems are touched."), not brief-specific sentences like the design's "the brief touches the existing claims system".
- **Skipped seats** are shown dashed in the strip with their reason (plan 12.3), which the design's 5-seat example does not need.
- **Tracker status pills** say "Blocker", "Condition" or "Client to confirm" from each item's severity and kind; the design mixes "Open", "Condition" and "Blocker". The log lists O items first, then C items.
- **Header** adds "N of M can proceed" (plan 4.4 rule 5); the seconds are measured from the first seat starting to the last finishing.
- **Next step:** the Bid Manager arrives in Phase 4, so "Next: the Bid Manager answers the objections" is shown disabled with a note instead of the design's handoff line.
- **On a phone** the objections log stacks each row instead of a four-column table.
- **Model badge** names the model that answered, as in Phase 2 (on Gemini the model's own name; on the judged gateway "Sonnet" or "Haiku").

### Phase 3 gate (local, Gemini, 28 Nov 2026)

- Northwind: discover 2.9 s, draft 5.0 s, board 2.3 s; 5 seats; 1 of 5 can proceed; 8 tracker items.
- Harbor Freight: discover 1.7 s, draft 4.3 s, board 2.4 s; 4 seats (the accepted Phase 2 deviation; a later run chose the expected 3); 1 of 4; 7 items.
- Summit Ridge: discover 2.5 s, draft 4.9 s, board 2.2 s; 5 seats; 1 of 5; 9 items.
- Every seat answered on its first try. Forced failures (one scoring seat, one gate, fewer than 2 seats) and the retry are covered by fake-model tests, because a live model cannot be made to fail on demand.

## Phase 4

- **One request per round.** `POST /api/revise` with `{state, round_no}` runs one Bid Manager round and one re-vote of every seat in `board_plan`; the run state travels in the browser. The server refuses a round number that does not follow the last one, and any round after code stopped the loop, so there are never more than 3 board votes. HMAC signing of the run state (`STATE_SECRET`) is a Phase 6 item and is not used yet.
- **Stop rules (`domain/loop.py: stop_decision`)**, checked after every board vote, naming every rule that holds: every seat can proceed; the last round improved nothing (average scoring-seat score up by less than `MIN_GAIN = 0.2` and no more seats able to proceed); the Bid Manager round limit (2, or 1 in Lite mode); the per-run cost guard (`RUN_COST_CAP_USD = 0.25`, a soft guard from section 9.4, summed from the step records). A Bid Manager or seat failure fails the stage with a Retry card instead of stopping the loop.
- **Bid Manager changes, applied by code (`domain/revision.py`):** each change must name an open objection id; a change to a calculated (locked) claim, an unknown claim, or with no text is refused and shown as refused. Items only the client can confirm (C items) can only be answered with an assumption ("Confirm with the client: …"); code refuses anything else. Applied changes mark the item "answered", never "fixed". New and changed claims pass the quote and number guards (G10, G9) before the board reads them. Changes are at most 20 words, not counting the "Confirm with the client:" prefix.
- **Fixed means re-read (G14):** in a re-vote each seat gets its own open items and the changes since the last draft, and returns `previous` with resolved, partly or open per id. Only the raising seat's "resolved" fixes an item; other seats' ids and unknown ids are ignored. For a gate seat that does not list one of its own items, its checklist answer for that line counts as its re-read (met = resolved, partly = partly, not met = open), and a line that already has an open item gets no second one. History stores the board round of the re-read; the page shows "Fixed R1" for "fixed by Bid Manager round 1".
- **Report (`POST /api/report`, `domain/report.py`)** is assembled by code with no model call: the verdict by section 4.7, the headline "Draft 1 scored X. After N revision rounds it scored Y." (average scoring-seat score), four key numbers (average score first → last; objections fixed X of Y with "+N conditions to confirm"; Phase 1 cost and total from the cost calculator; go-live from the schedule, or "To confirm"), what changed since draft 1, the decision memo (each seat's reason picked by code from its own words: its condition, else its first open item, else its lowest-rated criterion's reason; for a gate, its unmet lines), and the open C items to confirm with the client.
- **Print and download:** "Print or save as PDF" calls `window.print()`; the print stylesheet hides the header, stage bar, other screens and buttons, prints the verdict as an outlined box, keeps small blocks whole and lets long cards break between rows. "Download this run" saves the run state plus the report as JSON.
- **Code split:** the stage 4 and 5 renderers live in `static/js/render-loop.js` (reusing helpers from `render.js`) so `render.js` stays readable. Node screen tests share `tests/js/fake-dom.mjs`; the integration tests share the fake-model fixture in `tests/integration/conftest.py`.

### Differences from the design (Phase 4)

- **Not built yet (by plan phase):** the QA Reviewer card (Phase 7) is hidden; the report's run timeline and run details (Phase 7) are not shown; meeting prep (Phase 8) shows a placeholder with the code-built "Confirm with the client" list; the prototype button (Phase 8) is disabled; the currency line ("≈ €…") and holiday-aware go-live arrive with the public tools in Phase 5.
- **Tracker statuses** add "Answered" (the Bid Manager changed the proposal but the seat has not agreed yet) beside the design's "Fixed R1", "Confirm" and an "Open" state.
- **Refused changes** are listed in each round card ("Refused by code: a calculated claim is locked (C3)."), which the design does not show.
- **Verdict banner colours** follow the verdict: green for Approved and Approved with conditions (as in the design), dark amber for Review incomplete, dark red for Not ready yet.
- **"How failures are handled"** link on the report is left out until the states screen (Phase 6).

### Phase 4 gate (local, Gemini, 28 Nov 2026)

- Northwind: discover 1.9 s, draft 5.1 s, board 2.2 s, revise 13.6 s and 6.0 s, report 0.04 s; 3 board votes; stopped by "no gain" and "round limit"; Not ready yet (5.8 → 6.3; 5 of 9 objections fixed).
- Harbor Freight: discover 1.4 s, draft 3.8 s, board 2.3 s, revise 5.7 s, report 0.02 s; 2 board votes; stopped by "no gain"; Not ready yet (5.1 → 5.3).
- Summit Ridge: discover 2.1 s, draft 4.1 s, board 1.9 s, revise 21.8 s and 6.0 s, report 0.03 s; 3 board votes; stopped by "no gain" and "round limit"; Not ready yet (6.0 → 6.6; 6 of 7 fixed).
- A round after the stop was refused (`input_blocked`) every time. The gate script paused 15 s between stages to stay under the free key's per-minute limit; a run through the page without pauses hit that limit in round 2 and showed the Retry card, as designed.
- Seen live and addressed: the Bid Manager rewrote a claim to answer a client-only item (now refused by code) and added near-duplicate assumptions across rounds (prompt now forbids repeating one).

### Phase 4 follow-up (live Vercel run of Northwind)

- **Commercial facts stay the client's (`domain/claims.py: is_protected`, `states_commercial_fact`).** The Bid Manager may not replace or remove a claim that comes from the brief or is calculated, a claim in the team-and-cost or timeline section, or any claim about contract type, rate, price, cost, team size or dates; nor may it add or write such a statement. Code refuses it as "protected" ("commercial facts, dates and brief claims can only change through an assumption"), listed with the other refused changes. The only allowed answer is an assumption, for example "Confirm with the client: Lumen Works could offer a not-to-exceed cap of $24,000 on top of time and materials." The prompt says the same. The check is a word list (contract terms, money, rate, cap, engineers, weeks, months, go-live, ISO dates); payment and acceptance terms are not on it, since the board may ask for those clauses.
- **No open objection is skipped silently (`services/revise.py`).** Open items go to the Bid Manager blockers first. If its answer names no change for an open fixable objection (O ids), code retries it once with `answer_these_now` listing the missing ids, blockers first, and keeps only the retry's changes for those ids. The two calls show as one step (time, tokens and cost added up, status "retried"). Ids still missing are stored in the round (`not_answered`) and shown on the revisions card and in the report under "Not answered by the Bid Manager" (only those still open). C items need no answer.
- **Gate items read as the seat's reason (`domain/tracker.py: checklist_text`, `checklist_hint`).** Without the seat's own objection text, an item is "Access control: <the seat's reason>." and its hint "Add access control as the seat described: <reason>."; the decision memo's gate row shows the same text.
- **Each client-only item once.** A C item raised again by the same seat on the same claims updates the open item (same id, new text); a near-identical text (lower case, punctuation and the "Confirm with the client:" prefix removed) from any seat is merged into the first; an assumption claim whose normalized text already exists is not added (from the Proposal Manager, from code, or from the Bid Manager, which code refuses as "duplicate"). The "Confirm with the client" list is deduplicated the same way, so it and the "conditions to confirm" count show each item once.
- **Wording:** the go-live note is "Weekends skipped; public holidays not checked yet" and the assumption is "the dates count weekdays only; public holidays are not checked yet."
- **Where an added statement goes:** the Bid Manager may name one of the nine sections in `section`; otherwise the section of the claim the objection points to, else Proposed solution. An unknown section name counts as none.
- **Follow-up gate (local, Gemini, 28 Nov 2026):** Northwind 3 board votes, stopped by "no gain" and "round limit", Not ready yet (6.2 → 7.1, 3 of 5 objections fixed); Harbor Freight 2 votes, "no gain", Not ready yet (5.5 → 5.3); Summit Ridge 3 votes, "no gain" and "round limit", Not ready yet (6.2 → 6.5, 4 of 4 fixed). Every open objection was answered on the first call (no retry needed, nothing under "Not answered"); no applied change touched the contract model; code refused 5 repeated assumptions as duplicates; each "Confirm with the client" list had no repeats.

### Phase 4 follow-up 2 (live Vercel run of Northwind)

- **Why O2's change was refused.** An "add" with no text is refused as "empty" before any other check, so the "protected" outcome means the Bid Manager's sentence matched the commercial word list. Claim C7 played no part: for "add" only the new text is checked. The broad list caught ordinary commitments (words such as "cost", "engineer-days", "weeks", and "may" as a month). Code never stored a refused change's text, which is why the run state showed no `new_text`. Refused changes now keep it in `proposed_text`.
- **The commercial check is narrower.** It now looks for figures and contract terms only: contract type, cap, ceiling, not-to-exceed, discount, a day or hourly rate, a lower or new price, amounts of money, a number of people, days, weeks or months, and calendar dates (a month name counts only with a day or year). "A written change request states the effect on engineer-days and cost" passes.
- **Only an applied change answers an objection.** A refused or invalid change leaves the objection unanswered, so it goes into the retry. The retry gets `refused_changes`: each refused change's text, why code refused it and how to fix it. For "add" and "assume", code ignores any claim_id the model sends and assigns the new id itself. What is still unanswered after the retry is listed in `not_answered`.
- **"No gain" waits for every blocker.** The loop does not stop on "no gain" while an open fixable blocker, or an item from a must-have gate line (`TrackerItem.must`), has never had an applied change. In that case the next round runs if the round limit and cost guard allow it. Decisions for Lumen Works (below) do not hold the loop, since no proposal change can settle them.
- **Our own terms versus client facts.** The Bid Manager prompt now says that change control, acceptance and payment terms, data protection, access control, rollback and handover are ours to state. It writes these as concrete commitments in generic words, with no invented standards or figures (no TLS or AES versions, SLAs or payment days). Only what the client alone knows (IT availability, budget approval, internal data rules, who joins a pilot) becomes "Confirm with the client: …". The commercial-fact rule is unchanged.
- **Tags.** Any claim in Assumptions, or starting "Confirm with the client:", is stored as origin "assumption" and shows TO CONFIRM. This covers the Proposal Manager's draft, a Bid Manager add and a Bid Manager replace. Calculated claims never change.
- **Repeated objections.** An O item raised again by the same seat, on the same claim or the same checklist line, with similar text, updates the open item and keeps its id. A blocker stays a blocker. "Similar" means at least half (`SIMILAR_TEXT_OVERLAP`) of the shorter text's content words appear in the other; content words are 4 letters or more (`CONTENT_WORD_MIN`), compared lower case without punctuation.
- **The commercial model claim.** The Proposal Manager prompt said "time and materials with a cap", copied from the plan's section list. It now says to state only the contract type from the flag. Code also checks the draft: if a claim mentions a cap, ceiling or not-to-exceed and the brief does not, the claim becomes "The commercial model is time and materials." (or "fixed price"), taken from the flag. If the flag is unclear, it becomes an assumption asking the client for the commercial model.
- **Decisions for Lumen Works.** An open O item that asks to change our commercial terms is flagged `decision`. That means it asks for a cap, ceiling, not-to-exceed, discount or lower rate or price, or the other contract type (a firm fixed price on a time-and-materials brief). The tracker shows it as "Needs a Lumen Works decision", and the report lists it under "Decisions for Lumen Works" in the meeting-prep card. The Bid Manager sees it marked, must not change the contract model, and is not retried for it.
- **Follow-up 2 gate (local, Gemini, 28 Nov 2026):** Northwind 3 votes, stopped by "round limit", Not ready yet (6.2 → 7.2, 5 of 8 fixed). Harbor Freight 2 votes, "no gain", Not ready yet (6.5 → 5.7). Summit Ridge 3 votes, "round limit", Not ready yet (6.4 → 7.0, 6 of 10 fixed). No draft claimed a cap, and no assumption lacked its tag. The retry ran four times. Summit Ridge round 2 still left O1 and O7 unanswered, and they are listed. In Harbor Freight and Summit Ridge, change control was answered by a real commitment ("Scope changes are handled through a written change request that states the effect on engineer-days and cost."). In Northwind, Procurement raised change control as client-only (C1, `needs_client`), so code allowed only an assumption. Open point: a gate item about our own terms should never be client-only.

## Phase 4b: front-end redesign (design v12)

- **Scope:** front end only (`static/`, `tests/js/`). No API, schema, agent, prompt, rule, score or loop logic changed, and no dependency was added. The feature inventory taken before the redesign, with every line ticked and the changes listed, is `docs/frontend-inventory.md`.
- **Shell:** dark top bar with "by Lumen Works", "Simulation, not a prediction", a client chip, the mode chip and "Agent activity: On/Off". Left stage list with Done / Now / Next. Right Agent activity rail: on the Brief it shows "This run" (the existing facts and placeholders, unchanged) and the idle agents. On later stages it shows each measured step: name, status, seconds, short model label with the full name in a tooltip, and tool count. A live "Running" line shows while a request is out, and the stage total is marked "estimate from tokens". On the Report it shows a run summary of counted values. The toggle is remembered in localStorage inside try/catch and defaults to on. Below 1100 px the rail is a collapsed summary chip above the content; below 760 px the stage list is a horizontal strip.
- **Model labels:** the server's badge, or the model's own name cut to 14 characters with "…", never wrapping; the full name and tier are in the tooltip (`shortModel`, `modelTitle` in `render.js`).
- **Adopted items A to I** from the v12 README are built as specified:
  - A: hero with "Watch the sample run" (disabled, existing hint) and "Start with this brief".
  - B: seats strip.
  - C: threshold line, ratings behind "Ratings and reasons".
  - D: gate chips from the gate answer only.
  - E: objections table, without "What changed" on the Client board and with it on Revisions.
  - F: score ring read from the report's "Average score, scoring seats" value, never computed in the browser, hidden in print.
  - G: "Close these items" box.
  - H: four shared message boxes.
  - I: tracker item layout.
- **"What to fix first"** is ordered by code in the browser from the open O items: blockers first, then objections of scoring seats below their needed score, then the rest. A Lumen Works decision is labelled as such. C items are left out, since only the client can settle them.
- **Kept although the mockups show less:** model badge and time on each agent block and seat card, the full tagged draft 1 (collapsed), scores by round as bars with the needed tick, the per-round change lists, "Nothing is waiting for the client.", and the "Decided by code" notes.
- **Not built, by plan phase:** run timeline and run details (Phase 7, no placeholder existed), QA Reviewer card (Phase 7), Risk & Compliance Analyst and public-API tool rows (Phase 5; the "PUBLIC API" tag style exists, unused), Presales Lead questions and prototype (Phase 8, existing placeholders kept), upload and passcode (switched off, with hints), the link to the states screen (Phase 6). There is no "live runs left" count, because the run data has no such number.
- **Deviations from the mockups:**
  - The hero keeps the app's existing heading and paragraph rather than the mockup's new sentence, so no honest label disappears.
  - Agent blocks are open at every width.
  - The upload box keeps today's hint rather than the planned limits, because upload is off.
  - The verdict banner keeps today's colours (green, amber, red by verdict), as README item F says.
- **Checks:** Playwright is not installed, and adding it would be a new dependency. Screenshots were therefore taken by driving the installed Edge over the DevTools protocol, using Node's built-in WebSocket, with a scratch script that is not in the repo. That script replays one real Northwind run recorded on Gemini, through the real page, at 1280 and 390 px wide. It also checks horizontal overflow (0 px on every screen at both widths) and prints the report to PDF (4 pages). The screenshots are in `docs/screenshots/v12/`.
