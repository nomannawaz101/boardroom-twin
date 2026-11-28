# Front-end feature inventory (before the v12 redesign)

Written before the Phase 4b redesign from `static/index.html`, `static/js/*.js` and `static/css/style.css` on main. Every line below is ticked: the redesigned page (branch `phase-4b-redesign`) still has it, checked on the screenshots in `docs/screenshots/v12/` taken from a recorded Northwind run. Lines that moved or changed form are listed under "What changed" at the end.

## Whole page

- [x] Dark header: logo mark, "Boardroom Twin", "by Lumen Works"
- [x] Header chip "Simulation, not a prediction"
- [x] Mode chip (hidden until known): "Full mode" (green), "Lite mode" (amber), "Sample run" (yellow); set from `/api/health`, then from the run
- [x] Brand line shows "<client> · draft 1 / board round 1 / revisions / final report" on stages 2 to 5
- [x] Stage bar: five stages (Brief, Proposal team, Client board, Revisions, Report), each a button; a stage that is not open yet is disabled; the current stage has `aria-current="step"`; done stages get a "✓"
- [x] Clicking an open stage shows it (the Revisions and Report views re-render from the run state); page scrolls to the top
- [x] Footer: "Lumen Works is a fictional firm. All client names and briefs are made up." and "Every number is decided by code, not by AI."
- [x] Focus ring on every control; 44 px minimum touch targets; `[hidden]` always hides
- [x] Reduced-motion: cards fade in only when motion is allowed
- [x] No `localStorage` use today (the run state lives in memory only)
- [x] All AI text inserted as text nodes (`h()` helper); no HTML sinks (tested)
- [x] No outside URLs or CDN (tested)

## Screen 1: Brief

- [x] Hero heading "Rehearse your proposal in front of the client's board, before you send it." and its paragraph
- [x] "How it works": four step cards (STEP 1 to 4) with their texts
- [x] Card "Client brief", note "Paste text or pick a sample"
- [x] Sample buttons loaded from `/static/sample/briefs.json`: title + subtitle (contract type), `aria-pressed`; picking one fills client, country and brief; the first sample is picked on load
- [x] Client name field (max 200)
- [x] Country select (server list, tested) with hint "Used for public holidays and currency"
- [x] Brief textarea with hint ("Free text is fine… never invented.") and live counter "N / 15,000 characters" (`aria-live`), red and bold when over the limit
- [x] Upload box, disabled, with "Or upload a client document" and "PDF, Word and text upload arrives in a later build. For now, paste the text into the box above."; disabled file input
- [x] Tick box "This is public or made-up information…" (never ticked by code)
- [x] Code checks line: "Code checks before any AI call:" real-data scan, hidden-instruction scan, "is this a client brief?", and "Text inside a document is treated as data, never as instructions."
- [x] Privacy paragraph (full text)
- [x] Start card: "Watch the sample run" disabled with "The recorded sample run arrives in a later build."
- [x] "Start a live run with my brief" button (disabled while busy)
- [x] Start message area (`role="alert"`): browser checks (tick box, empty brief, over the limit) and server input errors ("Check the brief.", "Too long.", "This doesn't look like a client brief.")
- [x] Facts: Agent roles (from `/api/health`: "N, with T tools so far"), Board "3 to 5 seats, chosen from your brief", Time "About 2 to 3 minutes for a full run", Cost "≈ $0.16 per run (estimate)", Mode pill + model note (e.g. "Sonnet and Haiku", "Haiku only", "Recorded run")

## Screen 2: Proposal team

- [x] Eyebrow "STAGE 2 OF 5", title "The proposal team is writing draft 1" → "…wrote draft 1", intro text
- [x] Stat chips: N agents, N tool calls, "N s · $X.XX est." with the tooltip "Estimated from token counts at list prices. It is not a bill." (tested)
- [x] Notices: "Instructions aimed at an AI." warnings from discover
- [x] Relay of numbered agent cards with a rail line; each card: label, model badge (short label, tooltip "Answered by <model> (<tier> tier)"), time and tool count, summary, flag notes (retried, fallback, skipped, fixed order, partial), "Hands to …" line
- [x] Business Analyst: goal chips, warning chips (quote in tooltip), context flags (personal data, existing systems, contract, function, level), Input checks tool box (Code, no AI), board strip with joined seats (why in tooltip) and "(not needed)" seats
- [x] Solution Architect: parts grid (name + purpose)
- [x] Delivery Manager: tool boxes (tool name, "Code, no AI", input, result) and the "Locked cost" box
- [x] Proposal Manager card
- [x] Working card with a live seconds counter while a stage runs; Retry card ("This step did not finish", Retry this step, Back to the brief)
- [x] Draft summary: "Proposal, draft 1", "9 sections · N claims", "Proposal for <client>", Cost, Team, Start, Go-live ("To confirm" when missing), the nine section names, "Next: send it to the client board →"
- [x] Full proposal: legend of tags (FROM BRIEF, CALCULATED, TO CONFIRM, "Recommendations carry no tag."), nine numbered sections with claim ids and tags

## Screen 3: Client board

- [x] Eyebrow "STAGE 3 OF 5 · BOARD ROUND 1", title (reviewing / reviewed), intro built from the seat counts
- [x] Stat chips: N seats, "X of Y can proceed", "Verdict so far: …" (tooltip on the rule), "N s · $X.XX est." (span across seats, tooltip)
- [x] Board for this brief: "Chosen by code from the 5 flags…", "Code, no AI", joined seats (title, "Scores the proposal" / "Passes or blocks it", "Why: …"), skipped seats ("Not invited", "Why not: …"), note "Code chooses 3 to 5 seats per brief…"
- [x] Working card while seats review; Retry card on failure
- [x] Round 1 · scores: one card per scoring seat: avatar, title, model badge and seconds, decision pill, big score, "needs X.X", bar with needed tick (`aria-label`), criteria rows (label ×weight, rating or "not rated (0)", reason in tooltip), condition, partial note, quote
- [x] "Decided by code, not AI" note for scores
- [x] Round 1 · gates: one card per gate: checklist rows (icon with word as `aria-label`, label, MUST tag, "Partly: / Not met: reason"), partial note, quote
- [x] "Decided by code, not AI" note for gates
- [x] Not reviewed seat: warning text (scoring / gate / partial wording), answered items if any, "Retry this seat" (button text changes to "Retrying this seat…", error shown after it)
- [x] Objections log: ID, Raised by, Objection (+ claim ids), Status pill (Blocker / Condition / Client to confirm); "N open · O items…, C items…"; "No objections were raised."
- [x] Footer of the log: "The Bid Manager answers each objection by its ID…" or "Code stopped the loop here…", and the next button ("Next: the Bid Manager answers the objections →" or "Next: the final report →")

## Screen 4: Revisions

- [x] Eyebrow "STAGE 4 OF 5 · UP TO 2 BID MANAGER ROUNDS", title (answering / answered N objections in N rounds / stopped before a round), intro
- [x] Stat chips: N agent calls, "N s · $X.XX est." (tooltip)
- [x] Loop chips: "Board round 1: X of Y can proceed" → "Bid round N → Board round M: X of Y" → "Stopped by code" / "Bid Manager working…" / "Next round"
- [x] Per round card: "Bid Manager · round N", model badge, seconds, "answered …"; changes (ID, action word, old text struck, new text, "Removed."); refused changes in words with claim id; "Not answered by the Bid Manager." rows; re-vote rows (seat, before → after score or "gate", decision pill, note: condition / still open ids / "Nothing open." / "Did not answer; retry the seat."); "Hands to Bid Manager: …" line until the loop stops
- [x] Working card and Retry card per round
- [x] Scores by round: per scoring seat, bars per round with the needed tick, "not reviewed"; "The black tick is the score each executive needs."
- [x] Gates by round: per gate, chips "R1: …" → "R2: …"
- [x] Why the loop stopped: code's lines, or "The loop is still running"; note on the stop rules
- [x] Objection tracker: ID, text, status (Fixed Rn / Confirm / Needs a Lumen Works decision / Answered / Open) and the note on "fixed" vs "answered"
- [x] "Next: the final report →" once stopped

## Screen 5: Report

- [x] Working card while code assembles the report; Retry card
- [x] Verdict banner: colour by verdict (green, amber, red), "VERDICT", verdict, headline (draft 1 → final), summary; "Print or save as PDF" and "Download this run" (JSON with the run state and the report)
- [x] Key numbers: four cards (label, value, note)
- [x] What changed since draft 1 (ID, action and round, text; "No change was made…"); "Not answered by the Bid Manager" list
- [x] Final proposal with tags: "Proposal for <client> · final version (draft N)"
- [x] Board decision memo table: Seat, Result pill, Score ("X / Y", "gate" or "—"), Reason
- [x] Meeting prep: "The Presales Lead's questions and next steps arrive in a later build."; "Confirm with the client" list or "Nothing is waiting for the client."; "Decisions for Lumen Works" list when not empty
- [x] Prototype card: "See what Phase 1 could look like", "The UX Designer's concept screen arrives in a later build.", disabled "Show prototype preview"
- [x] "Start a new brief" button
- [x] Print: only the report; header, stage bar, footer, buttons and other views hidden; verdict as an outlined box; key numbers in four columns; small blocks kept whole; tables not clipped

## Selectors the JS tests depend on (tests/js)

- `render.js`: classes `crit` (2nd child is the rating), `bar` (`aria-label` "Score X of 10, needs Y"), `bar-fill` (`style` "width: N%"), `bar-tick` (`style` "left: N%"), `m-sonnet`, `m-haiku`, `must`, `ic` (`aria-label` = status word), `skipped`; `button` tags; objections table `tr` rows whose first cell is the ID; texts "Partly: …", "Not met: …", "Not answered: …", "(C7)", "3 open", "Blocker", "Condition", "Client to confirm", "Why: …", "Why not: …", "9 s · $0.02 est.", "Verdict so far: …"; `boardStats` returns three parts when there is no verdict.
- `render-loop.js`: `del` for old text; `m-sonnet`; `loop-stop`; `bar` / `bar-tick` in scores by round (`aria-label` "Round N: X, needs Y"); tracker `pill` elements in order (only the status chips carry `pill`); `verdict-bad` / `verdict-good` on the banner element; exactly one `no-print` inside the banner; banner buttons in order Print, Download; text checks on every function's output.
- `tests/unit/test_static_page.py`: `id="country"` select options, `BRIEF_MAX_CHARS` in `state.js`, no HTML sinks, no outside URLs, the literal `` toFixed(2)} est.` `` in `render.js`.

## What changed (all features kept)

- **Brand line** "<client> · draft 1 …" moved from the header's sub-line to its own client chip in the top bar; "by Lumen Works" now stays on every stage (design v12 shell).
- **Stage bar** became the left stage list: a status dot and the word Done / Now / Next replace the "✓"; not-yet-open stages are still disabled buttons, done stages still open their screen. On phones it is a horizontal strip that scrolls inside itself.
- **localStorage**: now used once, for the "Agent activity: On/Off" toggle (key `boardroom-twin.activity`, read and written inside try/catch). The run state still lives in memory only.
- **Start card facts** (Agent roles, Board, Time, Cost, Mode and model note) moved into the Agent activity rail as "This run", unchanged in wording ("≈ $0.16 per run (estimate)", "About 2 to 3 minutes for a full run"). On narrow screens they sit inside the collapsed rail chip; with the rail switched off they are hidden until it is switched on again.
- **"Watch the sample run"** is now the main button of the hero (item A) and is also kept in the Start card; both are disabled with the same hint, "The recorded sample run arrives in a later build." The hero adds "Start with this brief", which scrolls to the brief and focuses it.
- **Code checks** show as three green check chips with a "Code, before AI" label (item A); the wording is unchanged.
- **Start card** adds a disabled passcode field with the hint "Passcodes for live runs arrive in a later build. Live runs need none for now."; nothing else changed.
- **Agent cards** became collapsible blocks (`details`, open by default) with the number, name and summary in the header line; model badge, seconds and tool count stay on each block. The vertical rail line between cards is gone. A "Ran at the same time" marker appears when two steps' measured times overlap (none do today).
- **Draft summary** moved below the agent blocks; Cost, Team, Start and Go-live are boxes; the nine section names are chips.
- **Full draft 1 with tags** is kept, collapsed behind "Read the full draft 1, claim by claim, with tags".
- **Board for this brief** became the seats strip (item B): one tile per seat with its "Why" line and, once voted, its vote chip; skipped seats keep "Not invited" and "Why not".
- **Verdict so far** is also shown as a message box above the board (the stat chip stays).
- **Score cards**: the criteria rows moved behind "Ratings and reasons" (item C); each rating now shows its reason as text inside, and the tooltip stays. A threshold line was added under the bar.
- **Gate rows** add a Met / Partly / Not met / Not answered chip taken from the gate answer (item D); the "Partly: …" / "Not met: …" reason text stays.
- **Objections log**: the column "Objection" is now "Challenge" (item E). On phones the table scrolls inside its box instead of stacking each row.
- **Next button on the Client board** moved below the new "What to fix first" card; the log keeps its footer line.
- **Revisions**: each round is two cards, the Bid Manager's changes and the board vote that followed. Scores by round, gates by round, why the loop stopped and the tracker moved from the side column into the main column, since the right column is now the Agent activity rail. An "Objections and what changed" table was added (item E); the tracker, the per-round change lists and scores by round stay.
- **Tracker item** layout (item I): ID, then the text at full width, the status chip on its own line under it.
- **Why the loop stopped** and "Code stopped the loop here" use the info message box (item H).
- **Report**: the verdict banner adds a score ring (item F) read from the report's own "Average score, scoring seats" number; the ring is hidden in print, the numbers stay. The memo and meeting prep are stacked instead of side by side.
- **Meeting prep**: "Confirm with the client" and "Decisions for Lumen Works" are shown only inside the new "Close these items" box (item G); an empty list is hidden, and the box is hidden when both are empty. "Nothing is waiting for the client." stays when there is nothing to confirm.
- **Messages** (item H): one set of four boxes (ok, info, warning, error) restyled for every existing notice; class names `m-ok`, `m-info`, `m-warn`, `m-err` are unchanged or new.

## Test selectors after the redesign

No existing assertion in `tests/js` had to change: every class, attribute and text the tests read is still produced. New checks were added in `tests/js/shell.test.mjs` (rail, model labels, toggle storage), `board_screen.test.mjs` (seats strip vote chip, threshold line, gate chips, what to fix first, verdict box) and `loop_screens.test.mjs` (objections and what changed, tracker layout, score ring, close these items).

## Follow-up 1 (wording and layout), all features kept

- Every visible name for a code, id or role now comes from `static/js/labels.js`; the renames are listed in `docs/wording.md`. Texts that changed wording only: stage bar labels stay; "gates" → "sign-off checks", "seats" → "reviewers", "claims" → "statements", role names, tracker statuses, "Code, no AI" → "Fixed rules", "Context flags" → "Key facts from the brief", "Full mode" → "Live run".
- Brief: the hero heading is now "Know what the client's board will challenge, before the meeting."; the previous paragraph, both buttons, sample buttons, upload box, tick box and code checks are unchanged.
- Proposal team: the Business Analyst's goals, warnings (with their quotes), key facts, input checks and board are shown as lists, a key-value table, an ok box and one line, instead of chips. The draft summary's nine section names are a two-column numbered list.
- Client board: new "Board scoreboard" table; nothing removed.
- Revisions: same content, reordered top-down; earlier rounds and the objections table are collapsed (open on click). Sign-off checks by round moved into the "Why the loop stopped" card.
- Report: the "Confirm with the client" and "Decisions for you" lists moved from Meeting prep to "What to do next" under the verdict; "Nothing is waiting for the client." stays in Meeting prep. New "Scores by reviewer" card. "What changed" shows the objection in words with its #id.
- Legend lines added under each stage intro and at each page foot (hidden in print).
- Client board: the "Verdict so far" header chip was removed because the same verdict shows in the box below it; the chip's tooltip moved to the box.
- Activity rail: reviewers are named by their board titles, the same as on the board.
- Objection tables: text columns clamp to two lines; the full text is in the tooltip.
