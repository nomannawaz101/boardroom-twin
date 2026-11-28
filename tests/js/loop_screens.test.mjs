// Revisions and report screens, rendered by static/js/render-loop.js against the fake DOM.

import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { byClass, byTag, holderOf } from "./fake-dom.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const loop = await import(pathToFileURL(path.join(here, "..", "..", "static", "js", "render-loop.js")).href);

const seat = (id, title, fields) => ({ seat_id: id, kind: "scoring", title, status: "answered", able: true, needed: 7.0, ...fields });
const roundOne = {
  no: 1, progress: { able: 2, total: 3 },
  seats: [
    seat("cfo", "CFO", { score: 5.3, vote: "rejected", decision: "Rejected", able: false }),
    seat("vp_director", "VP, Claims", { score: 7.1, vote: "yes_with_condition", decision: "Yes, with a condition" }),
    { seat_id: "security", kind: "gate", title: "Security Officer", status: "answered", able: true, outcome: "pass_with_conditions", decision: "Pass, with conditions" },
  ],
};
const roundTwo = {
  no: 2, progress: { able: 3, total: 3 },
  seats: [
    seat("cfo", "CFO", { score: 8.0, vote: "approved", decision: "Approved" }),
    seat("vp_director", "VP, Claims", { score: 8.4, vote: "yes_with_condition", decision: "Yes, with a condition", condition: "Confirm the peak" }),
    { seat_id: "security", kind: "gate", title: "Security Officer", status: "answered", able: true, outcome: "pass", decision: "Pass" },
  ],
};
const tracker = [
  { id: "O1", seat: "cfo", kind: "O", severity: "blocker", text: "Smaller first step", status: "fixed", answered_in: [1], history: [{ round: 2, state: "resolved" }], claim_ids: [] },
  { id: "O2", seat: "vp_director", kind: "O", severity: "condition", text: "January peak", status: "open", answered_in: [1], history: [{ round: 2, state: "partly" }], claim_ids: [] },
  { id: "O3", seat: "vp_director", kind: "O", severity: "blocker", text: "Nobody answered this", status: "open", answered_in: [], history: [], claim_ids: [] },
  { id: "C1", seat: "security", kind: "C", severity: "condition", text: "Retention rule", status: "open", answered_in: [1], history: [], claim_ids: [] },
];
const bidRound = {
  no: 1, draft_no: 2, answered: ["C1", "O1"],
  changes: [
    { objection_id: "O1", action: "replace", claim_id: "C1", old_text: "One payment.", new_text: "Two phases.", outcome: "applied" },
    { objection_id: "O2", action: "replace", claim_id: "C3", old_text: "Go-live: Mon Jan 4, 2027.", new_text: null, outcome: "locked" },
    { objection_id: "C1", action: "assume", claim_id: "C6", old_text: null, new_text: "Confirm with the client: the retention rule.", outcome: "applied" },
  ],
};
const step = { agent: "bid_manager", tier: "sonnet", model: "claude-sonnet-5-5", badge: "Sonnet", duration_ms: 10200 };

// One Bid Manager round: old text struck, refusals in words, every seat's re-vote.
{
  const card = loop.bidRoundCard(bidRound, step, roundOne, roundTwo, tracker, false);
  const text = card.textContent;
  assert.match(text, /Revision Editor · round 1/);
  assert.match(text, /answered Q1, #1/);
  assert.equal(byTag(card, "del")[0].textContent, "One payment.");
  assert.match(text, /Refused by code: a calculated statement is locked \(S3\)\./);
  assert.match(text, /5\.3 → 8\.0 ▲/);
  assert.match(text, /Confirm the peak \(#2, #3\)/);
  assert.match(text, /sign-off/);
  assert.equal(byClass(card, "m-sonnet")[0].textContent, "Sonnet");
  assert.match(text, /Hands to Revision Editor: the open objections \(#2, #3\) and 1 condition\./);
  const last = loop.bidRoundCard(bidRound, step, roundOne, roundTwo, tracker, true);
  assert.doesNotMatch(last.textContent, /Hands to Bid Manager/);
}

// Loop chips and the stop.
{
  const running = holderOf(loop.loopChips([roundOne, roundTwo], { stopped: false }, true)).textContent;
  assert.match(running, /Board round 1: 2 of 3 reviewers can approve/);
  assert.match(running, /Revision round 1 → Board round 2: 3 of 3/);
  assert.match(running, /Revision Editor working/);
  const stopped = holderOf(loop.loopChips([roundOne, roundTwo], { stopped: true }, false));
  assert.equal(byClass(stopped, "loop-stop")[0].textContent, "Stopped by code");
  const why = holderOf(loop.whyStopped({ stopped: true, reasons: ["all_proceed"], lines: ["Every seat on the board can proceed."] }));
  assert.match(why.textContent, /Why the loop stopped/);
  assert.match(why.textContent, /Every reviewer can proceed\./);
}

// Scores and gates by round, with the needed-score tick.
{
  const scores = holderOf([...loop.scoresByRound([roundOne, roundTwo]), ...loop.gatesByRound([roundOne, roundTwo])]);
  const labels = byClass(scores, "bar").map((b) => b.attrs["aria-label"]);
  assert.deepEqual(labels.slice(0, 2), ["Round 1: 5.3, needs 7.0", "Round 2: 8.0, needs 7.0"]);
  assert.equal(byClass(scores, "bar-tick")[0].attrs.style, "left: 70%");
  assert.match(scores.textContent, /R1: Signed off, with conditions/);
  assert.match(scores.textContent, /R2: Signed off/);
}

// Tracker: fixed only after the seat agreed; answered is not fixed.
{
  const list = holderOf(loop.trackerList(tracker));
  const pills = byClass(list, "pill").map((p) => p.textContent);
  assert.deepEqual(pills, ["Resolved in round 1", "Changed, awaiting re-read", "Open", "Ask the client"]);
}

// The report: banner by verdict, key numbers, memo, meeting prep placeholder.
{
  const report = {
    verdict_code: "not_ready", verdict: "Not ready yet",
    headline: "Draft 1 scored 6.2. After 2 revision rounds it scored 6.8.",
    summary: "2 of 3 board seats can proceed.",
    numbers: [{ label: "Objections fixed", value: "1 of 3", note: "+1 condition to confirm" }],
    changes: [{ objection_id: "O1", round: 1, action: "Changed", text: "Two phases." }],
    memo: [{ seat_id: "security", title: "Security Officer", decision: "Blocked", outcome: "blocked", score: null, needed: null, reason: "Access control: not met" },
           { seat_id: "cfo", title: "CFO", decision: "Approved", vote: "approved", score: 8.0, needed: 7.0, reason: "Fits" }],
    confirm_with_client: ["Retention rule"],
  };
  let printed = false;
  let downloaded = false;
  const banner = loop.verdictBanner(report, () => { printed = true; }, () => { downloaded = true; });
  assert.ok(banner.className.includes("verdict-bad"));
  assert.match(banner.textContent, /Not ready yet/);
  assert.match(banner.textContent, /Draft 1 scored 6\.2\. After 2 revision rounds it scored 6\.8\./);
  const [printButton, downloadButton] = byTag(banner, "button");
  assert.equal(printButton.textContent, "Print or save as PDF");
  printButton.listeners.click();
  downloadButton.listeners.click();
  assert.ok(printed && downloaded);
  assert.equal(byClass(banner, "no-print").length, 1);
  assert.match(holderOf(loop.keyNumbers(report.numbers)).textContent, /1 of 3\+1 item for the client to confirm/);
  const memo = holderOf(loop.decisionMemo(report.memo)).textContent;
  assert.match(memo, /Blocked/);
  assert.match(memo, /sign-off/);
  assert.match(memo, /8\.0 \/ 7\.0/);
  assert.match(holderOf(loop.changesSince(report.changes, [], tracker)).textContent, /Smaller first step #1Changed, round 1Two phases\./);
  const long = [{ id: "O1", text: "A time and materials model does not provide a fixed cost ceiling, which is risky given our tight budget this year." }];
  const cut = byClass(holderOf(loop.changesSince(report.changes, [], long)), "change-obj")[0];
  assert.equal(cut.attrs.title, long[0].text);
  assert.match(cut.textContent, /^A time and materials model does not provide a fixed cost ceiling, which is risky given…\s#1$/);
  assert.doesNotMatch(holderOf(loop.changesSince(report.changes)).textContent, /Not answered/);
  const skipped = holderOf(loop.changesSince(report.changes, [{ objection_id: "O3", round: 1, action: "Not answered by the Bid Manager", text: "Access control: no single sign-on." }], tracker)).textContent;
  assert.match(skipped, /Not answered by the Revision Editor/);
  assert.match(skipped, /Nobody answered this #3round 1Access control: no single sign-on\./);
  const prep = holderOf(loop.meetingPrep(report.confirm_with_client)).textContent;
  assert.match(prep, /arrive in a later build/);
  assert.doesNotMatch(prep, /Retention rule/); // the list is in "What to do next" only
  assert.match(holderOf(loop.whatNext(report.confirm_with_client)).textContent, /Retention rule/);
  const approved = loop.verdictBanner({ ...report, verdict_code: "approved_with_conditions" }, () => {}, () => {});
  assert.ok(approved.className.includes("verdict-good"));
}

// Phase 4 follow-up: a refused commercial change and an objection the Bid Manager left out.
{
  const round = {
    ...bidRound,
    not_answered: ["O3"],
    changes: [{ objection_id: "O2", action: "add", claim_id: "C3", old_text: null, new_text: null, outcome: "protected" }],
  };
  const text = loop.bidRoundCard(round, step, roundOne, roundTwo, tracker, false).textContent;
  assert.match(text, /Refused by code: commercial facts, dates and brief statements can only change through an assumption \(S3\)\./);
  assert.match(text, /#3Not answered by the Revision Editor\./);
  const plain = loop.bidRoundCard(bidRound, step, roundOne, roundTwo, tracker, false).textContent;
  assert.doesNotMatch(plain, /Not answered/);
}

// Follow-up 2: a terms change is a decision for Lumen Works, in the tracker and the report.
{
  const decided = [{ id: "O4", seat: "cfo", kind: "O", severity: "blocker", text: "A firm fixed price", status: "open", decision: true, answered_in: [], history: [], claim_ids: [] }];
  assert.match(holderOf(loop.trackerList(decided)).textContent, /#4A firm fixed priceNeeds your decision/);
  const next = holderOf(loop.whatNext(["Retention rule"], ["A firm fixed price"])).textContent;
  assert.match(next, /Decisions for you/);
  assert.match(next, /A firm fixed price/);
  assert.doesNotMatch(holderOf(loop.whatNext(["Retention rule"])).textContent, /Decisions for you/);
}

// v12: objections and what changed (E); the tracker item keeps its text whole (I).
{
  const revisions = [
    { ...bidRound, changes: [...bidRound.changes, { objection_id: "O1", action: "add", claim_id: "C9", old_text: null, new_text: "A later, longer answer.", outcome: "applied" }] },
  ];
  const table = holderOf(loop.objectionsTable(tracker, roundOne.seats, revisions));
  const rows = byTag(table, "tr").slice(1).map((r) => r.children.map((c) => c.textContent));
  assert.deepEqual(rows[0], ["#1", "CFO", "Smaller first step", "AddedA later, longer answer.", "Resolved in round 1"]);
  assert.equal(rows[1][3], "Not changed by the Revision Editor"); // O2's change was refused
  assert.equal(rows[3][3], "AssumptionConfirm with the client: the retention rule.");
  assert.equal(byClass(table, "one-line")[0].attrs.title, "A later, longer answer.");
  const decided = [{ id: "O4", seat: "cfo", kind: "O", severity: "blocker", text: "A firm fixed price", status: "open", decision: true, answered_in: [], history: [], claim_ids: [] }];
  const item = byClass(holderOf(loop.trackerList(decided)), "tracker-row")[0];
  assert.deepEqual(item.children.map((c) => c.className), ["num tracker-id", "tracker-text", "tracker-status"]);
}

// v12: the score ring reads the report's own average (F); "Close these items" (G).
{
  const numbers = [{ label: "Average score, scoring seats", value: "5.9 → 6.5", note: "" }];
  assert.equal(loop.finalAverage(numbers), "6.5");
  assert.equal(loop.finalAverage([{ label: "Average score, scoring seats", value: "To confirm" }]), null);
  assert.equal(loop.finalAverage([]), null);
  const report = { verdict_code: "not_ready", verdict: "Not ready yet", headline: "Draft 1 scored 5.9. After 2 revision rounds it scored 6.5.", summary: "", numbers };
  const banner = loop.verdictBanner(report, () => {}, () => {});
  const ring = byClass(banner, "score-ring")[0];
  assert.equal(ring.attrs.style, "--p: 65");
  assert.equal(ring.attrs["aria-label"], "Final average score 6.5 of 10");
  assert.match(banner.textContent, /6\.5of 10/);
  assert.equal(byClass(banner, "no-print").length, 1);
  assert.equal(byClass(loop.verdictBanner({ ...report, numbers: [] }, () => {}, () => {}), "score-ring").length, 0);
  const both = holderOf(loop.whatNext(["Retention rule"], ["A firm fixed price"]));
  assert.match(both.textContent, /What to do nextConfirm with the clientRetention ruleDecisions for youA firm fixed price/);
  const onlyDecision = holderOf(loop.whatNext([], ["A firm fixed price"])).textContent;
  assert.doesNotMatch(onlyDecision, /Confirm with the client/);
  assert.equal(loop.whatNext([], []).length, 0); // the box is hidden
  assert.match(holderOf(loop.meetingPrep([])).textContent, /Nothing is waiting for the client\./);
}

// Score moves: up, down or the same, with the note that scores can move either way.
{
  assert.equal(loop.scoreMove(5.3, 8.0).className, "move move-up");
  assert.equal(loop.scoreMove(7.4, 6.1).className, "move move-down");
  assert.equal(loop.scoreMove(6.1, 6.1).className, "move move-same");
  assert.equal(loop.scoreMove(6.1, null).textContent, "6.1 → —");
  const moves = holderOf(loop.scoreMoves([roundOne, roundTwo])).textContent;
  assert.match(moves, /CFO5\.3 → 8\.0 ▲/);
  assert.match(moves, /VP, Claims7\.1 → 8\.4 ▲/);
  assert.match(moves, /Scores can move either way/);
  const golive = holderOf(loop.keyNumbers([{ label: "Go-live", value: "Mon Mar 22, 2027", note: "" }]));
  assert.equal(byClass(golive, "key-value")[0].textContent, "Mar 22, 2027");
  assert.equal(byClass(golive, "key-day")[0].textContent, "Monday");
}

process.stdout.write("loop screens: all checks passed\n");
