# Design v12 (approved by Muhammad, 28 Nov 2026; updated after design review, same day)

Reference for the front-end redesign. Replaces the layout of design/1..5 PNGs. Prototype and States screens are NOT redrawn: keep the current ones.
Files: 1-brief, 2-proposal-team, 3-client-board, 4-revisions, 5-report (.png = how it must look at 1280 wide, .html = static markup and CSS to copy from) and 6-components (.html, .png and a phone-width .png): the patterns adopted after the design review. WHERE 6-COMPONENTS AND THE SECTION "Adopted after review" BELOW DIFFER FROM THE 1-5 MOCKUPS, 6 AND THIS README WIN.

## Rules
1. Front-end only. Plain HTML, CSS and JS, system fonts, no frameworks, no CDN. Do not change any API, schema, agent, rule or score logic.
2. KEEP EVERY existing feature and every honest label. Nothing in the current app may disappear. Where a screen below shows less than the app does today, the app wins: keep it (collapsed, if needed).
3. All AI text is inserted as plain text (textContent), never as HTML.

## Shell (all five screens)
- Dark top bar: product name, "by Lumen Works", chip "Simulation, not a prediction", client chip and "Sample run" chip when relevant, and a button "Agent activity: On/Off".
- Left stage list: Brief, Proposal team, Client board, Revisions, Report. Each shows a status dot and Done / Now / Next. Done stages are links back.
- Middle column: ONLY decision content (verdicts, scores, reasons, objections, proposal). Detail per agent sits in collapsible blocks (details/summary), open by default on desktop.
- Right rail "Agent activity": per agent name, status (Waiting / Running with seconds so far / Done), measured seconds, SHORT model label (Sonnet, Haiku, or the real model name shortened, full name in a title tooltip), tool count, and stage cost marked "estimate from tokens". Visible by default on desktop, toggle button hides it and remembers the choice in localStorage (try/catch). On phones the rail becomes a collapsed summary chip above the content.
- Model badge must never wrap or overflow: short label + tooltip.
- Phone width: stage list becomes a horizontal strip, columns stack, wide tables scroll inside a box.

## Per screen
- Brief: steps, sample buttons (with contract type), client name, country, brief box with counter, upload box (PDF 20 pages / .docx / .txt, 3.5 MB), tick box (never auto-ticked), code checks list, privacy text, "Watch the sample run", passcode + "Start a live run", right rail = "This run" facts + idle agent list, footer link to the fallbacks/states.
- Proposal team: one collapsible block per agent with what it did and its tool calls (Code / PUBLIC API tags), "ran at the same time" marker, "Hands to" lines, proposal summary with key numbers and nine sections, next button.
- Client board: verdict banner ("Verdict so far"), board composition with "Why", three score cards (score, needed score tick, quote, ratings behind "Ratings and reasons"), "Decided by code" boxes, two gate cards with MUST checklists, objections log, "What to fix first" (derived by code from open objections: blocker first, then objections of seats below their needed score, then the rest), next button.
- Revisions: loop path line, Bid Manager changes per objection, QA Reviewer card (hidden until Phase 7), board votes per round with before-after scores, scores and gates by round, why the loop stopped, objection tracker.
- Report: verdict banner, Print/PDF and Download this run, four key numbers, what changed, proposal with tags, decision memo table, meeting prep, prototype entry (placeholders until Phase 8), run timeline, run details table; print CSS keeps the proposal and memo clean.

## Adopted after review (apply on top of screens 1 to 5; pattern shown in 6-components.html)
A. Brief: hero block above the form with one sentence on the value and two buttons, "Watch the sample run" (main) and "Start with this brief". The sample run stays switched off until it exists; show the button disabled with the existing "arrives in a later build" hint. Keep every other Brief element. Put the label "Code, before AI" on the code checks list.
B. Client board: seats strip at the top. One tile per seat: title, "Scores the proposal" or "Passes or blocks it", the existing "Why" line, and the vote chip once voted. Same data as today.
C. Score cards: keep the needed-score tick, add one threshold line under the bar ("The black tick is the score the CFO needs"). Sub-scores stay behind "Ratings and reasons".
D. Gate cards as checklist rows: round icon, item label, MUST tag, the seat's reason, and a right-hand chip Met / Partly / Not met. Chips come only from the gate answer.
E. Objections: table with ID, Raised by, Challenge (claim id in grey), What changed (chip Added / Changed / Assumption from the real change, then the new text on one line with ellipsis and the full text in title), Status. On the Client board omit the What changed column. Revisions keeps its per-round change list, objection tracker and scores by round; the table is added, not a replacement.
F. Report: verdict banner gets a score ring (final average of the scoring seats out of 10, set with a CSS variable, no JavaScript). The draft 1 to final text stays. Colour follows the verdict as today. In print the ring may be hidden; the numbers must stay.
G. Report, Meeting prep card: add a "Close these items" box at the bottom with two lists, "Confirm with the client" and "Decisions for Lumen Works". Both already exist in the run data. Hide an empty list; hide the box if both are empty. If the same lists are shown elsewhere today, keep them only in this box.
H. One shared set of four message boxes (ok, info, warning, error) used for every notice that exists today: input check results, upload problems, busy or retry messages, "Not reviewed" seats, stopped-by-code lines. Build the styles now; Phase 6 will add new messages that use them.
I. Bug fix, Revisions objection tracker: when the "Needs a Lumen Works decision" chip is shown the objection text wraps one word per line. Use the tracker item layout in 6-components (ID, then text at full width, chip on its own line). Check at 1280 and at phone width.

## Not part of this pass (do not build)
- No dark or ivory re-skin; keep the v12 palette. No new fonts or downloads.
- No invented metrics (alignment %, confidence, influence), no telemetry or uptime dashboards, no home or overview page, no history across runs (Vercel keeps nothing between requests).
- Run timeline and run details table: only when Phase 7 records start and end times per step. Leave the existing placeholder.
- Failure-state screens (retry countdown, budget used up, run modes): Phase 6. Only the message-box styles (H) now.

## Known content issues seen in the live run (NOT front-end; do not fix here, logged for later phases)
- Own commitments sit under Assumptions with a TO CONFIRM tag; near-duplicate claims; an invented cache age tagged TO CONFIRM.

Sample numbers in the mockups are the Northwind sample. The app must show real values. Never show a number or label that the run data does not contain.
