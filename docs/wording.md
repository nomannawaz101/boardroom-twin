# Wording: what the user sees

Every display name for an internal code, id or role lives in `static/js/labels.js`. A rename is one edit there and one line here. Internal codes, ids, API fields and the run JSON never change.

## Roles

| Shown | Replaces | Internal id |
|---|---|---|
| Revision Editor | Bid Manager | `bid_manager` |
| Proposal Writer | Proposal Manager | `proposal_manager` |
| Fact Checker | QA Reviewer | `qa_reviewer` |

Other role names are unchanged: Business Analyst, Solution Architect, Delivery Manager, Risk & Compliance Analyst, Presales Lead, and the seat titles.

## Board

| Shown | Replaces | Internal code |
|---|---|---|
| reviewer(s) | seat(s) | `seat_id`, `seats` |
| "5 reviewers", "0 of 5 reviewers can approve" | "5 seats", "0 of 5 can proceed" (also "can proceed" in code-written text) | `progress.able`, `progress.total` |
| Retry this reviewer / Retrying this reviewer… | Retry this seat / Retrying this seat… | `/api/board/retry` |
| "This reviewer did not answer." (status stays "Not reviewed") | "… couldn't answer …" | `status: not_reviewed` |
| scoring reviewers | scoring seats | `kind: scoring` |
| sign-off check(s), "Sign-off checks" | gate(s), "gates" | `kind: gate` |
| sign-off reviewer(s) | gatekeeper(s) | `kind: gate` |
| Signs off or blocks it | Passes or blocks it | `kind: gate` |
| Signs off (scoreboard role) | (new) | `kind: gate` |
| Signed off | Pass | `outcome: pass` |
| Signed off, with conditions | Pass, with conditions | `outcome: pass_with_conditions` |
| Blocked | Blocked | `outcome: blocked` |
| Required | MUST | `must: true` |
| "Sign-off reviewers answer three checklist questions. They do not give a score." | "Gatekeepers answer three checklist questions. …" | |
| Decided by fixed rules, not AI | Decided by code, not AI | |

## Proposal and ids

| Shown | Replaces | Data id |
|---|---|---|
| statement(s), "17 statements" | claim(s) | `claims` |
| S1, S2 … | C1, C2 … (proposal claims) | `claims[].id` = `C1` … |
| #1, #2 … | O1, O2 … (objections the proposal can fix) | `tracker[].id` = `O1` … |
| Q1, Q2 … | C1, C2 … (items only the client can answer) | `tracker[].id` = `C1` … |
| Final draft (draft 3) | final version (draft 3) | `draft_no` |

## Statuses

| Shown | Replaces | Code |
|---|---|---|
| Changed, awaiting re-read | Answered | `answered_in` not empty |
| Resolved in round 1 | Fixed R1 | `status: fixed` + history |
| Ask the client | Confirm, Client to confirm | `kind: C` |
| Needs your decision | Needs a Lumen Works decision | `decision: true` |
| Decisions for you | Decisions for Lumen Works | `report.decisions` |
| N items for the client to confirm | N conditions to confirm | `report.numbers` note |
| What to do next | Close these items | |
| Board scoreboard: Scores / Signs off, Score (needed), Biggest issue, "No open objections" | (new) | `kind`, `score`, `needed`, tracker |
| Scores by reviewer, draft 1 → final; ▲ ▼ = | (new) | `rounds[].seats[].score` |

## Tags and chips

| Shown | Replaces |
|---|---|
| Fixed rules | Code, no AI |
| Key facts from the brief | Context flags |
| Live run | Full mode |
| Lite run | Lite mode |
| Sample run | Sample run (unchanged) |

## Legends

- Under each stage intro: "AI = written by a model. Fixed rules = decided by code, the same every time."
- At the foot of each stage page: "Red = rejected or blocked. Amber = conditions or to confirm. Green = met or resolved. Purple = AI. Grey = fixed rules."

## Code-written server text

Step labels, summaries, handoff lines, stop lines, the report summary and the key-number labels and notes are written by code on the server. `codeText()` in `labels.js` shows them in the words above: role names, Pass → Signed off, seat → reviewer, claim → statement, gate → sign-off check, context flags → key facts, conditions to confirm → items for the client to confirm, and ids O1 → #1, and C1 → Q1 only when C1 is a client-only item in the current tracker (a statement id such as C7 stays as written). Model-written text (objections, quotes, conditions, reasons, proposal statements) is never rewritten.

## Tests that assert display strings (updated with the renames)

`tests/js/board_screen.test.mjs` and `tests/js/loop_screens.test.mjs`: the not-reviewed texts, "Retry this reviewer", shown ids (#1, Q1, S7), "Ask the client", reviewer counts, "Required item", "Signed off", the tracker statuses, "Revision Editor" lines, "items for the client to confirm", "Decisions for you". The assertions on internal codes, classes and attributes are unchanged.

## Reviewer names

Every screen, including the activity rail, names a reviewer by its seat title from the board plan (for example "VP, Customer Support"). Before the board plan is known, and for every other agent, the role label is used (`stepName()` in `labels.js`).

## Follow-up 2 additions

| Shown | Replaces |
|---|---|
| 6.4 of 10, needs 7.0 of 10 | 6.4, needs 7.0 |
| weight 40% | ×0.40 |
| Average score of the scoring reviewers (out of 10) | Average score, scoring seats |
| Objections resolved | Objections fixed |
| 4 items for the client to confirm | +4 conditions to confirm |
| 3 of 5 reviewers can approve this draft | 3 of 5 board seats can proceed |
| What they need (memo column) | Reason |
| Passes to … | Hands to … |
| board picker | Board composer |
| summary of the brief | case file |
| Cost fixed by code | Locked cost |
| N code calculations | N tool calls / N tools |
| AI steps | agent calls |
| Tokens (AI text units) | Tokens |
| Boardroom Twin: {stage} (tab title) | Boardroom Twin |
| Coming in the full build: meeting questions and a prototype preview. | the Meeting prep and prototype cards |

Takeaway lines under each stage title and the Brief intro line and five steps are also in `labels.js` or built in `static/js/takeaways.js` from run data.
