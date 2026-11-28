# Front-end feature inventory (before the v12 redesign)

Written before the Phase 4b redesign from `static/index.html`, `static/js/*.js` and `static/css/style.css` on main. Every line is ticked once the redesigned page still has it. Where it moved or changed, the note says how.

## Whole page

- [ ] Dark header: logo mark, "Boardroom Twin", "by Lumen Works"
- [ ] Header chip "Simulation, not a prediction"
- [ ] Mode chip (hidden until known): "Full mode" (green), "Lite mode" (amber), "Sample run" (yellow); set from `/api/health`, then from the run
- [ ] Brand line shows "<client> · draft 1 / board round 1 / revisions / final report" on stages 2 to 5
- [ ] Stage bar: five stages (Brief, Proposal team, Client board, Revisions, Report), each a button; a stage that is not open yet is disabled; the current stage has `aria-current="step"`; done stages get a "✓"
- [ ] Clicking an open stage shows it (the Revisions and Report views re-render from the run state); page scrolls to the top
- [ ] Footer: "Lumen Works is a fictional firm. All client names and briefs are made up." and "Every number is decided by code, not by AI."
- [ ] Focus ring on every control; 44 px minimum touch targets; `[hidden]` always hides
- [ ] Reduced-motion: cards fade in only when motion is allowed
- [ ] No `localStorage` use today (the run state lives in memory only)
- [ ] All AI text inserted as text nodes (`h()` helper); no HTML sinks (tested)
- [ ] No outside URLs or CDN (tested)

## Screen 1: Brief

- [ ] Hero heading "Rehearse your proposal in front of the client's board, before you send it." and its paragraph
- [ ] "How it works": four step cards (STEP 1 to 4) with their texts
- [ ] Card "Client brief", note "Paste text or pick a sample"
- [ ] Sample buttons loaded from `/static/sample/briefs.json`: title + subtitle (contract type), `aria-pressed`; picking one fills client, country and brief; the first sample is picked on load
- [ ] Client name field (max 200)
- [ ] Country select (server list, tested) with hint "Used for public holidays and currency"
- [ ] Brief textarea with hint ("Free text is fine… never invented.") and live counter "N / 15,000 characters" (`aria-live`), red and bold when over the limit
- [ ] Upload box, disabled, with "Or upload a client document" and "PDF, Word and text upload arrives in a later build. For now, paste the text into the box above."; disabled file input
- [ ] Tick box "This is public or made-up information…" (never ticked by code)
- [ ] Code checks line: "Code checks before any AI call:" real-data scan, hidden-instruction scan, "is this a client brief?", and "Text inside a document is treated as data, never as instructions."
- [ ] Privacy paragraph (full text)
- [ ] Start card: "Watch the sample run" disabled with "The recorded sample run arrives in a later build."
- [ ] "Start a live run with my brief" button (disabled while busy)
- [ ] Start message area (`role="alert"`): browser checks (tick box, empty brief, over the limit) and server input errors ("Check the brief.", "Too long.", "This doesn't look like a client brief.")
- [ ] Facts: Agent roles (from `/api/health`: "N, with T tools so far"), Board "3 to 5 seats, chosen from your brief", Time "About 2 to 3 minutes for a full run", Cost "≈ $0.16 per run (estimate)", Mode pill + model note (e.g. "Sonnet and Haiku", "Haiku only", "Recorded run")

## Screen 2: Proposal team

- [ ] Eyebrow "STAGE 2 OF 5", title "The proposal team is writing draft 1" → "…wrote draft 1", intro text
- [ ] Stat chips: N agents, N tool calls, "N s · $X.XX est." with the tooltip "Estimated from token counts at list prices. It is not a bill." (tested)
- [ ] Notices: "Instructions aimed at an AI." warnings from discover
- [ ] Relay of numbered agent cards with a rail line; each card: label, model badge (short label, tooltip "Answered by <model> (<tier> tier)"), time and tool count, summary, flag notes (retried, fallback, skipped, fixed order, partial), "Hands to …" line
- [ ] Business Analyst: goal chips, warning chips (quote in tooltip), context flags (personal data, existing systems, contract, function, level), Input checks tool box (Code, no AI), board strip with joined seats (why in tooltip) and "(not needed)" seats
- [ ] Solution Architect: parts grid (name + purpose)
- [ ] Delivery Manager: tool boxes (tool name, "Code, no AI", input, result) and the "Locked cost" box
- [ ] Proposal Manager card
- [ ] Working card with a live seconds counter while a stage runs; Retry card ("This step did not finish", Retry this step, Back to the brief)
- [ ] Draft summary: "Proposal, draft 1", "9 sections · N claims", "Proposal for <client>", Cost, Team, Start, Go-live ("To confirm" when missing), the nine section names, "Next: send it to the client board →"
- [ ] Full proposal: legend of tags (FROM BRIEF, CALCULATED, TO CONFIRM, "Recommendations carry no tag."), nine numbered sections with claim ids and tags

## Screen 3: Client board

- [ ] Eyebrow "STAGE 3 OF 5 · BOARD ROUND 1", title (reviewing / reviewed), intro built from the seat counts
- [ ] Stat chips: N seats, "X of Y can proceed", "Verdict so far: …" (tooltip on the rule), "N s · $X.XX est." (span across seats, tooltip)
- [ ] Board for this brief: "Chosen by code from the 5 flags…", "Code, no AI", joined seats (title, "Scores the proposal" / "Passes or blocks it", "Why: …"), skipped seats ("Not invited", "Why not: …"), note "Code chooses 3 to 5 seats per brief…"
- [ ] Working card while seats review; Retry card on failure
- [ ] Round 1 · scores: one card per scoring seat: avatar, title, model badge and seconds, decision pill, big score, "needs X.X", bar with needed tick (`aria-label`), criteria rows (label ×weight, rating or "not rated (0)", reason in tooltip), condition, partial note, quote
- [ ] "Decided by code, not AI" note for scores
- [ ] Round 1 · gates: one card per gate: checklist rows (icon with word as `aria-label`, label, MUST tag, "Partly: / Not met: reason"), partial note, quote
- [ ] "Decided by code, not AI" note for gates
- [ ] Not reviewed seat: warning text (scoring / gate / partial wording), answered items if any, "Retry this seat" (button text changes to "Retrying this seat…", error shown after it)
- [ ] Objections log: ID, Raised by, Objection (+ claim ids), Status pill (Blocker / Condition / Client to confirm); "N open · O items…, C items…"; "No objections were raised."
- [ ] Footer of the log: "The Bid Manager answers each objection by its ID…" or "Code stopped the loop here…", and the next button ("Next: the Bid Manager answers the objections →" or "Next: the final report →")

## Screen 4: Revisions

- [ ] Eyebrow "STAGE 4 OF 5 · UP TO 2 BID MANAGER ROUNDS", title (answering / answered N objections in N rounds / stopped before a round), intro
- [ ] Stat chips: N agent calls, "N s · $X.XX est." (tooltip)
- [ ] Loop chips: "Board round 1: X of Y can proceed" → "Bid round N → Board round M: X of Y" → "Stopped by code" / "Bid Manager working…" / "Next round"
- [ ] Per round card: "Bid Manager · round N", model badge, seconds, "answered …"; changes (ID, action word, old text struck, new text, "Removed."); refused changes in words with claim id; "Not answered by the Bid Manager." rows; re-vote rows (seat, before → after score or "gate", decision pill, note: condition / still open ids / "Nothing open." / "Did not answer; retry the seat."); "Hands to Bid Manager: …" line until the loop stops
- [ ] Working card and Retry card per round
- [ ] Scores by round: per scoring seat, bars per round with the needed tick, "not reviewed"; "The black tick is the score each executive needs."
- [ ] Gates by round: per gate, chips "R1: …" → "R2: …"
- [ ] Why the loop stopped: code's lines, or "The loop is still running"; note on the stop rules
- [ ] Objection tracker: ID, text, status (Fixed Rn / Confirm / Needs a Lumen Works decision / Answered / Open) and the note on "fixed" vs "answered"
- [ ] "Next: the final report →" once stopped

## Screen 5: Report

- [ ] Working card while code assembles the report; Retry card
- [ ] Verdict banner: colour by verdict (green, amber, red), "VERDICT", verdict, headline (draft 1 → final), summary; "Print or save as PDF" and "Download this run" (JSON with the run state and the report)
- [ ] Key numbers: four cards (label, value, note)
- [ ] What changed since draft 1 (ID, action and round, text; "No change was made…"); "Not answered by the Bid Manager" list
- [ ] Final proposal with tags: "Proposal for <client> · final version (draft N)"
- [ ] Board decision memo table: Seat, Result pill, Score ("X / Y", "gate" or "—"), Reason
- [ ] Meeting prep: "The Presales Lead's questions and next steps arrive in a later build."; "Confirm with the client" list or "Nothing is waiting for the client."; "Decisions for Lumen Works" list when not empty
- [ ] Prototype card: "See what Phase 1 could look like", "The UX Designer's concept screen arrives in a later build.", disabled "Show prototype preview"
- [ ] "Start a new brief" button
- [ ] Print: only the report; header, stage bar, footer, buttons and other views hidden; verdict as an outlined box; key numbers in four columns; small blocks kept whole; tables not clipped

## Selectors the JS tests depend on (tests/js)

- `render.js`: classes `crit` (2nd child is the rating), `bar` (`aria-label` "Score X of 10, needs Y"), `bar-fill` (`style` "width: N%"), `bar-tick` (`style` "left: N%"), `m-sonnet`, `m-haiku`, `must`, `ic` (`aria-label` = status word), `skipped`; `button` tags; objections table `tr` rows whose first cell is the ID; texts "Partly: …", "Not met: …", "Not answered: …", "(C7)", "3 open", "Blocker", "Condition", "Client to confirm", "Why: …", "Why not: …", "9 s · $0.02 est.", "Verdict so far: …"; `boardStats` returns three parts when there is no verdict.
- `render-loop.js`: `del` for old text; `m-sonnet`; `loop-stop`; `bar` / `bar-tick` in scores by round (`aria-label` "Round N: X, needs Y"); tracker `pill` elements in order (only the status chips carry `pill`); `verdict-bad` / `verdict-good` on the banner element; exactly one `no-print` inside the banner; banner buttons in order Print, Download; text checks on every function's output.
- `tests/unit/test_static_page.py`: `id="country"` select options, `BRIEF_MAX_CHARS` in `state.js`, no HTML sinks, no outside URLs, the literal `` toFixed(2)} est.` `` in `render.js`.
