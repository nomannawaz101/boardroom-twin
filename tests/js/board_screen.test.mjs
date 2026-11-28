// Board screen states, rendered by static/js/render.js against a tiny stand-in for the DOM.
// Run: node tests/js/board_screen.test.mjs  (pytest runs it through tests/unit/test_board_screen.py)

import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { FakeNode, byClass, byTag } from "./fake-dom.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const render = await import(pathToFileURL(path.join(here, "..", "..", "static", "js", "render.js")).href);

const step = { agent: "cfo", tier: "sonnet", model: "claude-sonnet-5-5", badge: "Sonnet", duration_ms: 8100 };
const answered = {
  seat_id: "cfo", kind: "scoring", title: "CFO", status: "answered", able: false, partial: false,
  score: 5.3, needed: 7.0, vote: "rejected", decision: "Rejected", condition: null,
  quote: "Is there a smaller first step?",
  criteria: [
    { id: "cost_clarity", label: "Cost clarity", weight: 0.4, rating: 7, reason: "clear" },
    { id: "value", label: "Value", weight: 0.35, rating: 5, reason: "ok" },
    { id: "budget_fit", label: "Budget fit", weight: 0.25, rating: null, reason: "" },
  ],
};
const notReviewed = {
  seat_id: "enterprise_architect", kind: "scoring", title: "Enterprise Architect",
  status: "not_reviewed", able: false, decision: "Not reviewed", criteria: [], needed: 8.0,
};
const gate = {
  seat_id: "security", kind: "gate", title: "Security Officer", status: "answered", able: false,
  partial: false, outcome: "blocked", decision: "Blocked", quote: "Who can see a claim?",
  items: [
    { id: "data_protection", label: "Data protection", must: true, status: "partly", reason: "not described" },
    { id: "access_control", label: "Access control", must: true, status: "not_met", reason: "who may see a claim" },
    { id: "data_rules_fit", label: "Fit with the client's data rules", must: false, status: "met", reason: "fine" },
  ],
};

// Answered scoring seat: score, needed score, bar and tick, criteria, badge, quote.
{
  const card = render.scoreCard(answered, step, () => {});
  const text = card.textContent;
  assert.match(text, /5\.3/);
  assert.match(text, /needs 7\.0/);
  assert.match(text, /Rejected/);
  assert.match(text, /not rated \(0\)/);
  const ratings = byClass(card, "crit").map((row) => row.children[1].textContent);
  assert.deepEqual(ratings, ["7", "5", "not rated (0)"]);
  assert.match(text, /"Is there a smaller first step\?"/);
  const bar = byClass(card, "bar")[0];
  assert.equal(bar.attrs["aria-label"], "Score 5.3 of 10, needs 7.0");
  assert.equal(byClass(card, "bar-fill")[0].attrs.style, "width: 53%");
  assert.equal(byClass(card, "bar-tick")[0].attrs.style, "left: 70%");
  assert.equal(byClass(card, "m-sonnet")[0].textContent, "Sonnet");
  assert.equal(byTag(card, "button").length, 0);
}

// Not reviewed seat: the state says so, and Retry this seat calls back.
{
  let retried = false;
  const card = render.scoreCard(notReviewed, undefined, () => { retried = true; });
  assert.match(card.textContent, /Not reviewed/);
  assert.match(card.textContent, /This reviewer did not answer\. The Enterprise Architect is shown as not reviewed\. The other reviewers' votes still count\./);
  const buttons = byTag(card, "button");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].textContent, "Retry this reviewer");
  buttons[0].listeners.click();
  assert.equal(retried, true);
  assert.equal(byClass(card, "bar").length, 0);
}

// Not reviewed gate: its own wording.
{
  const card = render.gateCard({ ...notReviewed, seat_id: "security", kind: "gate", title: "Security Officer" }, undefined, () => {});
  assert.match(card.textContent, /This sign-off check is not reviewed\. Until the Security Officer answers, it cannot sign off\./);
  assert.equal(byTag(card, "button")[0].textContent, "Retry this reviewer");
}

// Gate seat: MUST marks, status words and icons that say the status in words too.
{
  const card = render.gateCard(gate, { ...step, agent: "security", tier: "haiku", badge: "Haiku" }, () => {});
  assert.equal(byClass(card, "must").length, 2);
  assert.match(card.textContent, /Partly: not described/);
  assert.match(card.textContent, /Not met: who may see a claim/);
  assert.match(card.textContent, /Blocked/);
  const icons = byClass(card, "ic").map((n) => n.attrs["aria-label"]);
  assert.deepEqual(icons, ["Partly", "Not met", "Met"]);
  assert.equal(byClass(card, "m-haiku")[0].textContent, "Haiku");
}

// Objections log: one row per item, words for every status, the open count.
{
  const tracker = [
    { id: "C1", seat: "security", kind: "C", severity: "condition", claim_ids: [], text: "Retention rule unknown", status: "open" },
    { id: "O1", seat: "cfo", kind: "O", severity: "blocker", claim_ids: ["C7"], text: "No smaller first step", status: "open" },
    { id: "O2", seat: "security", kind: "O", severity: "condition", claim_ids: [], text: "Data protection: partly met.", status: "open" },
  ];
  const parts = render.objectionsLog(tracker, [answered, gate]);
  const holder = new FakeNode("section");
  holder.append(...parts);
  const rows = byTag(holder, "tr");
  assert.equal(rows.length, 4); // header + 3 rows
  assert.deepEqual(rows.slice(1).map((r) => r.children[0].textContent), ["#1", "#2", "Q1"]);
  const text = holder.textContent;
  for (const word of ["Blocker", "Condition", "Ask the client", "3 open", "(S7)", "Security Officer"]) {
    assert.ok(text.includes(word), `missing: ${word}`);
  }
}

// Board for this brief: joined and skipped seats with their reasons.
{
  const plan = {
    seats: [{ id: "cfo", kind: "scoring", title: "CFO", why: "Always on the board: owns the budget." }],
    skipped: [{ id: "security", title: "Security Officer", why_not: "No personal data is involved." }],
  };
  const holder = new FakeNode("section");
  holder.append(...render.boardPlan(plan));
  assert.match(holder.textContent, /Why: Always on the board/);
  assert.match(holder.textContent, /Why not: No personal data/);
  assert.equal(byClass(holder, "skipped").length, 1);
}

// Header stats: measured span across seats running at the same time, and progress.
{
  const steps = [
    { start_ms: 100, duration_ms: 8000, cost_usd: 0.01 },
    { start_ms: 120, duration_ms: 9000, cost_usd: 0.01 },
  ];
  const holder = new FakeNode("div");
  holder.append(...render.boardStats(steps, { able: 2, total: 5 }));
  assert.match(holder.textContent, /2 reviewers/);
  assert.match(holder.textContent, /2 of 5 reviewers can approve/);
  assert.match(holder.textContent, /9 s · \$0\.02 est\./);
  assert.equal(holder.children.length, 3); // no empty slot when there is no verdict yet
  const withVerdict = new FakeNode("div");
  withVerdict.append(...render.boardStats(steps, { able: 2, total: 5 }, { code: "not_ready", label: "Not ready yet" }));
  assert.match(withVerdict.textContent, /Verdict so far: Not ready yet/);
}

// Partial gate answer, Not reviewed: the answered items, the missing one in words, and Retry.
{
  let retried = false;
  const partial = {
    seat_id: "security", kind: "gate", title: "Security Officer", status: "not_reviewed",
    able: false, partial: true, decision: "Not reviewed", outcome: null,
    items: [
      { id: "data_protection", label: "Data protection", must: true, status: "met", reason: "described" },
      { id: "access_control", label: "Access control", must: true, status: "missing", reason: "Not answered by the seat." },
      { id: "data_rules_fit", label: "Fit with the client's data rules", must: false, status: "met", reason: "fine" },
    ],
  };
  const card = render.gateCard(partial, { ...step, agent: "security", tier: "haiku", badge: "Haiku" }, () => { retried = true; });
  const text = card.textContent;
  assert.match(text, /Not reviewed/);
  assert.match(text, /partial answer/);
  assert.match(text, /never counted as met or not met/);
  assert.match(text, /Not answered: Not answered by the seat\./);
  assert.deepEqual(byClass(card, "ic").map((n) => n.attrs["aria-label"]), ["Met", "Not answered", "Met"]);
  const buttons = byTag(card, "button");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].textContent, "Retry this reviewer");
  buttons[0].listeners.click();
  assert.equal(retried, true);
}

// Partial gate answer that a known must-have Not met blocks: Blocked, with the partial note.
{
  const blocked = {
    ...gate, partial: true,
    items: [
      { id: "data_protection", label: "Data protection", must: true, status: "not_met", reason: "not described" },
      { id: "access_control", label: "Access control", must: true, status: "missing", reason: "Not answered by the seat." },
      { id: "data_rules_fit", label: "Fit with the client's data rules", must: false, status: "met", reason: "fine" },
    ],
  };
  const card = render.gateCard(blocked, undefined, () => {});
  assert.match(card.textContent, /Blocked/);
  assert.match(card.textContent, /A required item it answered Not met blocks anyway/);
  assert.equal(byTag(card, "button").length, 0);
}

// v12: the seats strip shows each seat's vote once voted; the threshold line; gate chips.
{
  const plan = { seats: [{ id: "cfo", kind: "scoring", title: "CFO", why: "Owns the budget." }], skipped: [] };
  const before = new FakeNode("section");
  before.append(...render.boardPlan(plan));
  assert.equal(byClass(before, "pill").length, 0); // no vote chip before the vote
  const after = new FakeNode("section");
  after.append(...render.boardPlan(plan, { seats: [answered] }));
  assert.match(after.textContent, /Why: Owns the budget\.Rejected/);
  assert.match(render.scoreCard(answered, step, () => {}).textContent, /The black tick is the score the CFO needs\. Below it means Rejected\./);
  const chips = byClass(render.gateCard(gate, undefined, () => {}), "chk-chip").map((n) => n.textContent);
  assert.deepEqual(chips, ["Partly", "Not met", "Met"]);
}

// What to fix first: blockers, then seats below their needed score, then the rest; C items
// and fixed items are left out; a Lumen Works decision says so.
{
  const seats = [
    { seat_id: "cfo", title: "CFO", score: 5.3, needed: 7.0 },
    { seat_id: "vp_director", title: "VP", score: 7.5, needed: 7.0 },
    { seat_id: "security", title: "Security Officer", score: null },
  ];
  const tracker = [
    { id: "O1", seat: "vp_director", kind: "O", severity: "condition", text: "Peak week", status: "open" },
    { id: "O2", seat: "cfo", kind: "O", severity: "condition", text: "Smaller step", status: "open", decision: true },
    { id: "O3", seat: "security", kind: "O", severity: "blocker", text: "Access control", status: "open" },
    { id: "O4", seat: "cfo", kind: "O", severity: "blocker", text: "Done", status: "fixed" },
    { id: "C1", seat: "security", kind: "C", severity: "condition", text: "Retention", status: "open" },
  ];
  const list = new FakeNode("section");
  list.append(...render.fixFirst(tracker, seats));
  const items = byTag(list, "li").map((li) => li.textContent);
  assert.deepEqual(items, [
    "#3 (Security Officer, blocker): Access control",
    "#2 (CFO, reviewer below its needed score, needs your decision): Smaller step",
    "#1 (VP): Peak week",
  ]);
  assert.equal(render.fixFirst([], seats).length, 0);
}

// The verdict so far, in a message box by verdict.
{
  const box = render.verdictSoFar({ code: "not_ready", label: "Not ready yet" }, { able: 2, total: 5 });
  assert.ok(box.className.includes("m-err"));
  assert.match(box.textContent, /Verdict so far: Not ready yet2 of 5 reviewers can approve\./);
}

// Board scoreboard: role, score with the needed score (a dash for sign-off checks), result,
// and the biggest open issue picked by code.
{
  const tracker = [
    { id: "C1", seat: "cfo", kind: "C", severity: "blocker", text: "Client budget owner", status: "open", claim_ids: [] },
    { id: "O2", seat: "cfo", kind: "O", severity: "condition", text: "Smaller step", status: "open", claim_ids: [] },
    { id: "O3", seat: "cfo", kind: "O", severity: "blocker", text: "x".repeat(100), status: "open", claim_ids: [] },
    { id: "O4", seat: "security", kind: "O", severity: "blocker", text: "Done", status: "fixed", claim_ids: [] },
  ];
  assert.equal(render.biggestIssue(tracker, "cfo").id, "O3");
  assert.equal(render.biggestIssue(tracker, "security"), null);
  const table = new FakeNode("section");
  table.append(...render.scoreboard({ seats: [answered, gate] }, tracker));
  const rows = byTag(table, "tr").slice(1).map((r) => r.children.map((c) => c.textContent));
  assert.deepEqual(rows[0].slice(0, 4), ["CFO", "Scores", "5.3 (7.0)", "Rejected"]);
  assert.equal(rows[0][4], `${"x".repeat(80)}…`);
  assert.deepEqual(rows[1], ["Security Officer", "Signs off", "—", "Blocked", "No open objections"]);
}

process.stdout.write("board screen: all checks passed\n");
