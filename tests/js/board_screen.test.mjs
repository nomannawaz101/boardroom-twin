// Board screen states, rendered by static/js/render.js against a tiny stand-in for the DOM.
// Run: node tests/js/board_screen.test.mjs  (pytest runs it through tests/unit/test_board_screen.py)

import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.className = "";
    this.listeners = {};
    this.ownText = null;
  }
  append(...children) {
    for (const child of children) this.children.push(child);
  }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  get textContent() { return this.ownText ?? this.children.map((c) => c.textContent).join(""); }
  set textContent(value) { this.ownText = value; this.children = []; }
}

class FakeText extends FakeNode {
  constructor(text) { super("#text"); this.ownText = text; }
}

globalThis.Node = FakeNode;
globalThis.document = {
  createElement: (tag) => new FakeNode(tag),
  createElementNS: (ns, tag) => new FakeNode(tag),
  createTextNode: (text) => new FakeText(text),
};

const here = path.dirname(fileURLToPath(import.meta.url));
const render = await import(pathToFileURL(path.join(here, "..", "..", "static", "js", "render.js")).href);

function all(node, test, found = []) {
  if (test(node)) found.push(node);
  for (const child of node.children || []) all(child, test, found);
  return found;
}
const byClass = (node, cls) => all(node, (n) => (n.className || "").split(" ").includes(cls));
const byTag = (node, tag) => all(node, (n) => n.tag === tag);

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
  assert.match(card.textContent, /other seats' votes still count/);
  const buttons = byTag(card, "button");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].textContent, "Retry this seat");
  buttons[0].listeners.click();
  assert.equal(retried, true);
  assert.equal(byClass(card, "bar").length, 0);
}

// Not reviewed gate: its own wording.
{
  const card = render.gateCard({ ...notReviewed, seat_id: "security", kind: "gate", title: "Security Officer" }, undefined, () => {});
  assert.match(card.textContent, /this gate cannot pass/);
  assert.equal(byTag(card, "button")[0].textContent, "Retry this seat");
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
  assert.deepEqual(rows.slice(1).map((r) => r.children[0].textContent), ["O1", "O2", "C1"]);
  const text = holder.textContent;
  for (const word of ["Blocker", "Condition", "Client to confirm", "3 open", "(C7)", "Security Officer"]) {
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
  assert.match(holder.textContent, /2 seats/);
  assert.match(holder.textContent, /2 of 5 can proceed/);
  assert.match(holder.textContent, /9 s · \$0\.02 est\./);
}

process.stdout.write("board screen: all checks passed\n");
