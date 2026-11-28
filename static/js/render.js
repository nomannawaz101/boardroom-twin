// Builds every card from step records and responses. All AI text goes in as text nodes;
// no HTML string is ever parsed (guard G12).

import {
  BOARD_SUBTITLE, ISSUE_TEXT_MAX, needsText, outOf10, weightText, ITEM_WORDS, KIND_SHORT, KINDS, NO_OPEN, trimmed, OUTCOMES, STATUS, WORDS, codeText, objectionId, plural, reviewerCount,
  statementCount, statementId,
} from "./labels.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const SECTION_TITLES = {
  executive_summary: "Executive summary",
  client_situation: "Client situation",
  proposed_solution: "Proposed solution",
  scope: "Scope: in and out",
  timeline: "Timeline and milestones",
  team_cost: "Team and cost",
  risks: "Risks and mitigations",
  assumptions: "Assumptions",
  next_steps: "Next steps",
};
const TAGS = {
  brief: ["FROM BRIEF", "t-brief"],
  calculated: ["CALCULATED", "t-calc"],
  assumption: ["TO CONFIRM", "t-conf"],
};
const TOOL_NAMES = {
  cost_calculator: "Cost calculator",
  quote_checker: "Quote checker",
  working_days: "Working days",
};
const FLAG_NOTES = {
  retried: "Retried after a busy service or an answer code could not use.",
  fallback_fast: "The main model kept failing, so this step ran once on Haiku.",
  skipped: "The answer could not be used, so a safe default was used and marked.",
  fixed_order: "Tool choice was not available, so tools ran in a fixed order.",
  partial: "Partial answer.",
};
const CONTRACT = { fixed: "fixed price", tm: "time and materials", other: "other contract", none: "no contract" };
const LEVEL = { large: "VP (large deal)", small: "Director (small change)" };

export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svg(width, path, stroke) {
  const icon = document.createElementNS(SVG_NS, "svg");
  for (const [k, v] of Object.entries({
    width, height: width, viewBox: "0 0 24 24", fill: "none", stroke,
    "stroke-width": "2.2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true",
  })) icon.setAttribute(k, v);
  const line = document.createElementNS(SVG_NS, "path");
  line.setAttribute("d", path);
  icon.append(line);
  return icon;
}

// --- Formatting ---

export function money(amount, currency) {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency", currency, minimumFractionDigits: 0, maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}

export function longDate(iso) {
  const text = new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });
  return text.replace(",", "");
}

export function seconds(ms) {
  return `${(ms / 1000).toFixed(1)} s`;
}

function yesNo(value) {
  return value === true ? "yes" : value === false ? "no" : "unclear";
}

// --- Small parts ---

// The badge is decided by code on the server from the model that answered (after any
// fallback): a tier name only for that model family, otherwise the model's own name.
const MODEL_LABEL_MAX = 14;

// A short label that never wraps: the badge the server chose, or the model's own name cut to
// fit. The full name is always in the tooltip.
export function shortModel(step) {
  const name = String(step.badge || step.model || "").replace(/^models\//, "");
  return name.length > MODEL_LABEL_MAX ? `${name.slice(0, MODEL_LABEL_MAX - 1)}…` : name;
}

export function modelTitle(step) {
  return `Answered by ${step.model} (${step.tier} tier)`;
}

export function modelChip(step) {
  const family = step.badge === "Haiku" || (step.badge !== "Sonnet" && step.tier === "haiku") ? "m-haiku" : "m-sonnet";
  return h("span", { class: family, title: modelTitle(step) }, shortModel(step));
}

function codeChip() {
  return h("span", { class: "m-code" }, WORDS.fixedRules);
}

export function handLine(text) {
  const arrow = svg(14, "M5 12h14M13 6l6 6-6 6", "#5B3CC4");
  const match = /^Hands to (.+?): (.*)$/.exec(text || "");
  if (!match) return h("div", { class: "hand" }, arrow, text || "");
  return h("div", { class: "hand" }, arrow, "Hands to ", h("b", {}, match[1]), `: ${match[2]}`);
}

function flagNotes(step) {
  const notes = step.flags.map((f) => FLAG_NOTES[f]).filter(Boolean);
  return notes.length ? h("div", { class: "step-flags" }, notes.join(" ")) : null;
}

function rail(index, last, waiting = false) {
  return h(
    "div", { class: "rail" },
    h("span", { class: waiting ? "dot waiting" : "dot" }, String(index)),
    last ? null : h("span", { class: "rail-line", "aria-hidden": "true" }),
  );
}

// One block per agent (design v12): what it did in the summary line, the detail inside,
// open by default. Model and time stay on the block too, so nothing depends on the rail.
function agentCard(index, step, body) {
  const tools = step.tool_calls.length;
  const time = tools ? `${seconds(step.duration_ms)} · ${tools} ${tools === 1 ? "tool" : "tools"}` : seconds(step.duration_ms);
  const block = h(
    "details", { class: "card agent-block", open: true },
    h("summary", { class: "agent-sum" },
      h("span", { class: "agent-no" }, String(index)),
      h("strong", { class: "agent-name" }, codeText(step.label)),
      h("span", { class: "agent-summary" }, codeText(step.summary)),
      h("span", { class: "agent-meta" }, modelChip(step), h("span", { class: "num agent-time" }, time))),
    h("div", { class: "agent-in" },
      ...body,
      flagNotes(step),
      handLine(codeText(step.handoff_out))),
  );
  return h("li", { "data-agent": step.agent }, block);
}

// Two steps whose measured times overlap ran at the same time.
export function ranTogether(a, b) {
  return a.start_ms < b.start_ms + b.duration_ms && b.start_ms < a.start_ms + a.duration_ms;
}

export function togetherMarker() {
  return h("li", { class: "together" }, h("span", {}, "Ran at the same time"));
}

// --- Tool boxes ---

function toolInput(call) {
  const input = call.input || {};
  if (call.tool === "cost_calculator" && Array.isArray(input.phases)) {
    const phases = input.phases.map((p) => `${p.people} × ${p.days} days`).join(" + ");
    return `${phases} × ${money(input.rate, input.currency || "USD")}`;
  }
  if (call.tool === "quote_checker") return `"${input.quote ?? ""}"`;
  if (call.tool === "working_days") return `${input.start ?? "?"} to ${input.end ?? "?"}`;
  return "";
}

function toolResult(call) {
  const result = call.result || {};
  if (!call.ok) return ["Could not use that input", "bad"];
  if (call.tool === "cost_calculator") return [`= ${money(result.total, result.currency || "USD")}`, ""];
  if (call.tool === "quote_checker") return result.found ? ["Found in brief", "ok"] : ["Not in brief", "bad"];
  if (call.tool === "working_days") return [`${result.working_days} working days`, ""];
  return ["Done", ""];
}

function toolBox(call) {
  const [text, kind] = toolResult(call);
  return h(
    "div", { class: "tool" },
    h("span", { class: "tname" }, TOOL_NAMES[call.tool] || call.tool), codeChip(),
    h("span", { class: "num" }, toolInput(call)),
    h("strong", { class: `num tool-result ${kind}` }, text),
  );
}

// --- Stage 1: Business Analyst ---

function inputChecks(checks) {
  const injection = checks.injection === "notice" ? "instruction-like text kept as data" : "no hidden instructions";
  return h("div", { class: "msg m-ok input-ok" },
    codeChip(),
    h("span", {}, h("strong", {}, "Input checks: "), `No real personal data · ${injection} · looks like a client brief`));
}

function keyFacts(flags) {
  const rows = [
    ["Personal data", yesNo(flags.personal_data)],
    ["Existing systems", yesNo(flags.existing_systems)],
    ["Contract", CONTRACT[flags.contract_type] || "unclear"],
    ["Function", flags.function || "unclear"],
    ["Deal level", LEVEL[flags.seniority] || "unclear"],
  ];
  return [
    h("h3", { class: "block-h" }, WORDS.keyFacts),
    h("table", { class: "kv-table" }, h("tbody", {}, ...rows.map(([k, v]) => h("tr", {}, h("th", { scope: "row" }, k), h("td", {}, v))))),
    h("p", { class: "muted small" }, "Set by the Business Analyst. Code uses these to choose the board."),
  ];
}

function boardLine(plan) {
  const names = plan.seats.map((s) => s.title).join(", ");
  const skipped = plan.skipped.length ? ` · not needed: ${plan.skipped.map((s) => s.title).join(", ")}` : "";
  return h("p", { class: "board-line" },
    `Board chosen by fixed rules: ${reviewerCount(plan.seats.length)} `,
    h("span", { class: "muted" }, `(${names})${skipped}`));
}

export function analystCard(data) {
  const step = data.steps.find((s) => s.agent === "business_analyst");
  const caseFile = data.case_file;
  const facts = 5;
  const top = h("strong", { class: "block-top" },
    `${plural(caseFile.goals.length, "goal", "goals")}, ${plural(caseFile.warnings.length, "warning sign", "warning signs")}, ${facts} key facts.`);
  const wants = [
    h("h3", { class: "block-h" }, "What the client wants"),
    h("ul", { class: "plain-list" }, ...caseFile.goals.map((g) => h("li", {}, g))),
    h("h3", { class: "block-h" }, "Watch out for"),
    h("ul", { class: "plain-list watch-list" }, ...caseFile.warnings.map((w) => h("li", {},
      h("span", {}, w.text), h("span", { class: "quote-line" }, `"${w.quote}"`)))),
  ];
  const columns = h("div", { class: "two-cols" }, h("div", {}, ...wants), h("div", {}, ...keyFacts(data.flags)));
  return agentCard(1, step, [top, columns, inputChecks(data.checks), boardLine(data.board_plan)]);
}

// --- Stage 2: Solution Architect, Delivery Manager, Proposal Manager ---

export function architectCard(index, step, design, last) {
  const parts = h("div", { class: "parts" },
    ...design.parts.map((p, i) => h("div", { class: "part" },
      h("span", { class: "part-no" }, `Part ${i + 1}`), h("strong", {}, p.name), h("span", {}, p.purpose))));
  return agentCard(index, step, [parts]);
}

export function deliveryCard(index, step, data, last) {
  const body = step.tool_calls.map(toolBox);
  const estimate = data.estimate;
  if (estimate) {
    const phases = estimate.phases.map((p) => `${p.engineers} × ${p.days} days`).join(" + ");
    body.push(h(
      "div", { class: "tool" },
      h("span", { class: "tname" }, "Locked cost"), codeChip(),
      h("span", { class: "num" }, `${phases} × ${money(estimate.phases[0].rate, estimate.currency)}`),
      h("strong", { class: "num tool-result" }, `= ${money(estimate.total, estimate.currency)}`),
    ));
  }
  return agentCard(index, step, body);
}

export function managerCard(index, step) {
  return agentCard(index, step, []);
}

// --- Progress and failure cards ---

export function workingCard(index, text) {
  const timer = h("span", { class: "num agent-time" }, "0 s");
  const started = Date.now();
  const tick = setInterval(() => { timer.textContent = `${Math.round((Date.now() - started) / 1000)} s`; }, 1000);
  const card = h("div", { class: "card agent-card working", role: "status" },
    h("div", { class: "agent-head" }, h("strong", {}, "Working"), timer),
    h("span", { class: "agent-summary" }, text));
  const item = h("li", {}, rail(index, true, true), card);
  item.stop = () => clearInterval(tick);
  return item;
}

export function retryCard(index, message, onRetry, onBack) {
  const card = h(
    "div", { class: "card agent-card", role: "alert" },
    h("div", { class: "agent-head" }, h("strong", {}, "This step did not finish")),
    h("p", { class: "msg m-err" }, message, " Earlier stages are kept; nothing else is lost."),
    h("div", { class: "retry-row" },
      button("Retry this step", "btn btn-primary small-btn", onRetry),
      button("Back to the brief", "btn btn-plain small-btn", onBack)),
  );
  return h("li", {}, rail(index, true, true), card);
}

export function button(text, className, onClick, disabled = false) {
  const node = h("button", { type: "button", class: className, disabled }, text);
  if (onClick) node.addEventListener("click", onClick);
  return node;
}

export function message(kind, title, text) {
  return h("p", { class: `msg ${kind}` }, title ? h("strong", {}, `${title} `) : null, text);
}

// --- Draft summary and proposal ---

export function teamText(efforts) {
  if (!efforts || !efforts.length) return "To confirm";
  const engineers = Math.max(...efforts.map((e) => e.engineers));
  const weeks = efforts.reduce((sum, e) => sum + e.weeks, 0);
  return `${engineers} ${engineers === 1 ? "engineer" : "engineers"}, ${weeks} weeks`;
}

export function draftSummary(data, onNext) {
  const estimate = data.estimate;
  const schedule = data.schedule;
  const facts = [
    ["Cost", estimate ? money(estimate.total, estimate.currency) : "To confirm", true],
    ["Team", teamText(data.efforts), false],
    ["Start", schedule ? longDate(schedule.start) : "To confirm", true],
    ["Go-live", schedule ? longDate(schedule.go_live) : "To confirm", true],
  ];
  return [
    h("div", { class: "card-title-row" },
      h("h2", { id: "draft-h" }, "Proposal, draft 1"),
      h("span", { class: "muted small" }, `9 sections · ${statementCount(data.claims.length)}`)),
    h("strong", { class: "draft-title" }, `Proposal for ${data.case_file.client}`),
    h("dl", { class: "kv" },
      ...facts.map(([label, value, mono]) => h("div", {}, h("dt", {}, label), h("dd", { class: mono ? "num" : null }, value)))),
    h("ol", { class: "section-cols" }, ...Object.values(SECTION_TITLES).map((t) => h("li", {}, t))),
    h("div", {}, button("Next: send it to the client board →", "btn btn-primary", onNext)),
  ];
}

export function tagFor(origin) {
  const tag = TAGS[origin];
  return tag ? h("span", { class: `tag ${tag[1]}` }, tag[0]) : null;
}

export function proposal(claims, title = "Proposal, draft 1", headingId = "proposal-h") {
  const legend = h("div", { class: "legend" }, "Tags:",
    ...Object.values(TAGS).map(([text, cls]) => h("span", { class: `tag ${cls}` }, text)),
    "Recommendations carry no tag.");
  const sections = Object.entries(SECTION_TITLES).map(([id, title], i) => {
    // The server fills every section (code adds a TO CONFIRM line for any gap).
    const items = claims.filter((c) => c.section === id);
    const list = h("ul", {}, ...items.map((c) => h("li", {}, h("span", { class: "num claim-id" }, statementId(c.id)), c.text, " ", tagFor(c.origin))));
    return h("div", { class: "sec" }, h("h3", {}, `${i + 1}. ${title}`), list);
  });
  return [h("h2", { id: headingId }, title), legend, ...sections];
}

export function stats(steps) {
  const tools = steps.reduce((n, s) => n + s.tool_calls.length, 0);
  const ms = steps.reduce((n, s) => n + s.duration_ms, 0);
  const cost = steps.reduce((n, s) => n + s.cost_usd, 0);
  return [
    h("span", {}, `${steps.length} agents`),
    h("span", {}, `${tools} tool ${tools === 1 ? "call" : "calls"}`),
    h(
      "span",
      { class: "num", title: "Estimated from token counts at list prices. It is not a bill." },
      `${Math.round(ms / 1000)} s · $${cost.toFixed(2)} est.`,
    ),
  ];
}

// --- Stage 3: the client board ---

const AVATARS = {
  cfo: ["CFO", "#0F766E"],
  vp_director: ["VP", "#B45309"],
  enterprise_architect: ["EA", "#5B3CC4"],
  procurement: ["PC", "#1E4E8C"],
  security: ["SO", "#8C1D13"],
};
const DECISION_PILLS = {
  approved: "pill-good", yes_with_condition: "pill-cond", rejected: "pill-bad",
  pass: "pill-good", pass_with_conditions: "pill-cond", blocked: "pill-bad",
};
const FILLS = { approved: "fill-good", yes_with_condition: "fill-cond", rejected: "fill-bad" };
const CHIP_CLASSES = { met: "chip-good", partly: "chip-cond", not_met: "chip-bad", missing: "chip-none" };
const ITEM_ICONS = {
  met: ["✓", "ic-m", ITEM_WORDS.met],
  partly: ["~", "ic-p", ITEM_WORDS.partly],
  not_met: ["✕", "ic-n", ITEM_WORDS.not_met],
  missing: ["?", "ic-x", ITEM_WORDS.missing],
};

function avatar(seatId) {
  const [text, color] = AVATARS[seatId] || ["?", "#344054"];
  return h("span", { class: "av", style: `background: ${color}`, "aria-hidden": "true" }, text);
}

export function scoreText(score) {
  const fixed = score.toFixed(2);
  return fixed.endsWith("0") ? score.toFixed(1) : fixed;
}

// The vote or outcome in words; gate outcomes read as sign-offs.
export function decisionText(result) {
  return result.outcome && OUTCOMES[result.outcome] ? OUTCOMES[result.outcome] : result.decision;
}

export function decisionPill(result) {
  const key = result.vote || result.outcome;
  return h("span", { class: `pill ${DECISION_PILLS[key] || "pill-none"}` }, decisionText(result));
}

function seatHead(result, step) {
  const meta = step
    ? h("span", { class: "seat-meta" }, modelChip(step), h("span", { class: "num" }, seconds(step.duration_ms)))
    : null;
  return h("div", { class: "seat-head" },
    avatar(result.seat_id),
    h("div", { class: "seat-name" }, h("strong", {}, result.title), meta),
    decisionPill(result));
}

export function boardPlan(plan, round = null) {
  const voted = Object.fromEntries((round ? round.seats : []).map((s) => [s.seat_id, s]));
  const joined = plan.seats.map((s) => h("div", { class: "plan-seat" },
    h("strong", {}, s.title),
    h("span", { class: "muted" }, KINDS[s.kind] || KINDS.gate),
    h("span", { class: "why" }, `Why: ${s.why}`),
    voted[s.id] ? decisionPill(voted[s.id]) : null));
  const skipped = plan.skipped.map((s) => h("div", { class: "plan-seat skipped" },
    h("strong", {}, s.title),
    h("span", { class: "muted" }, "Not invited"),
    h("span", { class: "why" }, `Why not: ${s.why_not}`)));
  return [
    h("div", { class: "card-title-row" },
      h("div", { class: "stack-8" },
        h("h2", { id: "plan-h" }, "Board for this brief"),
        h("span", { class: "muted small" }, BOARD_SUBTITLE)),
      codeChip()),
    h("div", { class: "plan-grid" }, ...joined, ...skipped),
    h("span", { class: "muted small" }, "Fixed rules choose 3 to 5 reviewers per brief. Unclear facts make a reviewer join rather than skip."),
  ];
}

function notReviewedText(result) {
  if (result.partial) {
    return `${WORDS.notAnswered} The ${result.title} did not answer every checklist item, even after retries, so this ${WORDS.signOff} is not reviewed (partial answer). A missing item is never counted as met or not met.`;
  }
  return result.kind === "scoring"
    ? `${WORDS.notAnswered} The ${result.title} is shown as not reviewed. The other reviewers' votes still count.`
    : `${WORDS.notAnswered} This ${WORDS.signOff} is not reviewed. Until the ${result.title} answers, it cannot sign off.`;
}

function notReviewedBody(result, onRetry) {
  return [
    h("p", { class: "msg m-warn" }, h("strong", {}, "Not reviewed. "), notReviewedText(result)),
    result.items && result.items.length ? checklist(result.items) : null,
    button(WORDS.retryReviewer, "btn btn-outline small-btn retry-seat", onRetry),
  ];
}

function scoreBar(result) {
  const fill = h("span", { class: `bar-fill ${FILLS[result.vote]}`, style: `width: ${result.score * 10}%` });
  const tick = h("span", { class: "bar-tick", style: `left: ${result.needed * 10}%` });
  const label = `Score ${scoreText(result.score)} of 10, needs ${result.needed.toFixed(1)}`;
  return h("div", { class: "bar", role: "img", "aria-label": label }, fill, tick);
}

function quoteLine(result) {
  return result.quote ? h("p", { class: "seat-quote" }, `"${result.quote}"`) : null;
}

export function scoreCard(result, step, onRetry) {
  const head = seatHead(result, step);
  if (result.status === "not_reviewed") return h("article", { class: "card seat-card" }, head, ...notReviewedBody(result, onRetry));
  const criteria = result.criteria.map((c) => h("div", { class: "crit", title: c.reason || null },
    h("span", {}, `${c.label} · ${weightText(c.weight)}`),
    h("span", { class: "num" }, c.rating === null ? "not rated (0)" : ratingText(c.rating)),
    c.reason ? h("span", { class: "crit-reason" }, c.reason) : null));
  return h("article", { class: "card seat-card" },
    head,
    h("div", { class: "score-row" },
      h("span", { class: "num score-big" }, scoreText(result.score)),
      h("span", { class: "muted" }, "of 10 ·"),
      h("span", { class: "muted" }, needsText(result.needed))),
    scoreBar(result),
    h("p", { class: "threshold" }, `The black tick is the score the ${result.title} needs. Below it means Rejected.`),
    quoteLine(result),
    result.condition ? h("p", { class: "seat-note" }, `Condition: ${result.condition}`) : null,
    result.partial ? h("p", { class: "seat-note" }, "Partial answer: a criterion was not rated, so code counted it as 0.") : null,
    h("details", { class: "ratings" },
      h("summary", {}, "Ratings and reasons"),
      h("div", { class: "crit-list" }, ...criteria)));
}

function checklist(items) {
  const rows = items.map((item) => {
    const [icon, cls, word] = ITEM_ICONS[item.status];
    const reason = item.status === "met" ? item.reason : `${word}: ${item.reason}`;
    return h("div", { class: "chk" },
      h("span", { class: `ic ${cls}`, role: "img", "aria-label": word }, icon),
      h("div", { class: "chk-body" },
        h("div", {}, h("strong", {}, item.label), item.must ? h("span", { class: "must" }, WORDS.required) : null),
        h("span", { class: "chk-reason" }, reason)),
      h("span", { class: `chk-chip ${CHIP_CLASSES[item.status]}` }, word));
  });
  return h("div", { class: "chk-list" }, ...rows);
}

export function gateCard(result, step, onRetry) {
  const head = seatHead(result, step);
  if (result.status === "not_reviewed") return h("article", { class: "card seat-card" }, head, ...notReviewedBody(result, onRetry));
  return h("article", { class: "card seat-card" },
    head,
    checklist(result.items),
    result.partial ? h("p", { class: "seat-note" }, "Partial answer: an item was still not answered after the retries. A required item it answered Not met blocks anyway.") : null,
    quoteLine(result));
}

function ratingText(rating) {
  return Number.isInteger(rating) ? String(rating) : rating.toFixed(1);
}

function byTrackerOrder(a, b) {
  if (a.kind !== b.kind) return a.kind === "O" ? -1 : 1;
  return Number(a.id.slice(1)) - Number(b.id.slice(1));
}

function trackerPill(item) {
  if (item.kind === "C") return h("span", { class: "pill pill-cond" }, STATUS.askClient);
  return item.severity === "blocker"
    ? h("span", { class: "pill pill-bad" }, STATUS.blocker)
    : h("span", { class: "pill pill-cond" }, STATUS.condition);
}

export function objectionsLog(tracker, seats, next = null) {
  const titles = Object.fromEntries(seats.map((s) => [s.seat_id, s.title]));
  const open = tracker.filter((t) => t.status === "open");
  const rows = [...tracker].sort(byTrackerOrder).map((t) => h("tr", {},
    h("td", { class: "num" }, objectionId(t.id)),
    h("td", {}, titles[t.seat] || t.seat),
    h("td", {}, h("span", { class: "clamp2", title: t.text }, t.text,
      t.claim_ids.length ? h("span", { class: "num claim-id" }, ` (${t.claim_ids.map(statementId).join(", ")})`) : null)),
    h("td", {}, trackerPill(t))));
  const table = rows.length
    ? h("div", { class: "table-wrap" }, h("table", { class: "objections-table" },
        h("thead", {}, h("tr", {}, ...["ID", "Raised by", "Challenge", "Status"].map((c) => h("th", { scope: "col" }, c)))),
        h("tbody", {}, ...rows)))
    : h("p", { class: "log-foot muted" }, "No objections were raised.");
  return [
    h("div", { class: "log-head" },
      h("h2", { id: "obj-h" }, "Objections log"),
      h("span", { class: "muted small" }, `${open.length} open · # items the proposal can fix, Q items only the client can answer`)),
    table,
    h("div", { class: "log-foot next-row" },
      next && next.stopped
        ? h("span", { class: "msg m-info small" }, codeText("Code stopped the loop here: nothing for the Bid Manager to do."))
        : h("span", { class: "muted small" }, codeText("The Bid Manager answers each objection by its ID, then the board votes again.")),
      next && next.onClick ? button(next.label, "btn btn-primary", next.onClick) : null),
  ];
}

// What to fix first, ordered by code from the open objections: blockers first, then the
// objections of seats below their needed score, then the rest.
export function fixFirst(tracker, seats) {
  const bySeat = Object.fromEntries(seats.map((s) => [s.seat_id, s]));
  const below = (t) => {
    const seat = bySeat[t.seat];
    return Boolean(seat && seat.score !== null && seat.score !== undefined && seat.score < seat.needed);
  };
  const rank = (t) => (t.severity === "blocker" ? 0 : below(t) ? 1 : 2);
  const open = tracker.filter((t) => t.kind === "O" && t.status === "open")
    .sort((a, b) => rank(a) - rank(b) || byTrackerOrder(a, b));
  if (!open.length) return [];
  const why = ["blocker", "reviewer below its needed score", null];
  return [
    h("h2", {}, "What to fix first"),
    h("p", { class: "muted small" }, "Ordered by fixed rules: blockers first, then objections from reviewers below their needed score, then the rest."),
    h("ol", { class: "fix-list" }, ...open.map((t) => {
      const seat = bySeat[t.seat] ? bySeat[t.seat].title : t.seat;
      const notes = [why[rank(t)], t.decision ? STATUS.decision.toLowerCase() : null].filter(Boolean);
      return h("li", {}, h("strong", { class: "num" }, objectionId(t.id)), ` (${[seat, ...notes].join(", ")}): `, t.text);
    })),
  ];
}

// The reviewer's biggest open issue, chosen by code: a blocker before a condition, an objection
// the proposal can fix before an item for the client, then the tracker order.
export function biggestIssue(tracker, seatId) {
  const rank = (t) => (t.severity === "blocker" ? 0 : 2) + (t.kind === "O" ? 0 : 1);
  const open = tracker.filter((t) => t.seat === seatId && t.status === "open")
    .sort((a, b) => rank(a) - rank(b) || byTrackerOrder(a, b));
  return open.length ? open[0] : null;
}

// Board scoreboard: one row per reviewer of the latest vote.
export function scoreboard(round, tracker) {
  const rows = round.seats.map((s) => {
    const issue = biggestIssue(tracker, s.seat_id);
    const score = s.kind === "gate"
      ? "—"
      : `${s.score === null || s.score === undefined ? "—" : outOf10(scoreText(s.score))} (${needsText(s.needed).replace(" of 10", "")})`;
    return h("tr", {},
      h("td", {}, h("strong", {}, s.title)),
      h("td", { class: "nowrap" }, KIND_SHORT[s.kind] || KIND_SHORT.gate),
      h("td", { class: "num nowrap" }, score),
      h("td", {}, decisionPill(s)),
      h("td", issue ? { title: issue.text } : {}, issue ? trimmed(issue.text, ISSUE_TEXT_MAX) : h("span", { class: "muted" }, NO_OPEN)));
  });
  return [
    h("div", { class: "log-head" }, h("h2", {}, "Board scoreboard"),
      h("span", { class: "muted small" }, "Scores out of 10, with the score each reviewer needs; biggest open issue picked by fixed rules")),
    h("div", { class: "table-wrap" }, h("table", { class: "scoreboard" },
      h("thead", {}, h("tr", {}, ...["Reviewer", "Role", "Score", "Result", "Biggest issue"].map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", {}, ...rows))),
  ];
}

// The verdict so far, in one of the shared message boxes.
const VERDICT_RULE = "Decided by fixed rules: a known Rejected or Blocked wins; otherwise a reviewer not reviewed gives Review incomplete.";
const VERDICT_BOXES = { not_ready: "m-err", review_incomplete: "m-warn", approved_with_conditions: "m-warn", approved: "m-ok" };
export function verdictSoFar(verdict, progress) {
  return h("div", {
    class: `msg ${VERDICT_BOXES[verdict.code] || "m-info"} verdict-so-far`,
    title: VERDICT_RULE,
  },
    h("strong", {}, `Verdict so far: ${verdict.label}`),
    h("span", {}, `${progress.able} of ${reviewerCount(progress.total)} can approve. Fixed rules decided it from the reviewers' answers.`));
}

// The verdict so far is shown once, in its message box under the header, not as a chip here.
export function boardStats(steps, progress) {
  const starts = steps.map((s) => s.start_ms);
  const ends = steps.map((s) => s.start_ms + s.duration_ms);
  const spanMs = steps.length ? Math.max(...ends) - Math.min(...starts) : 0;
  const cost = steps.reduce((n, s) => n + s.cost_usd, 0);
  return [
    h("span", {}, reviewerCount(steps.length)),
    h("span", {}, `${progress.able} of ${reviewerCount(progress.total)} can approve`),
    h("span", { class: "num", title: "Time from the first reviewer starting to the last one finishing. Cost is estimated from token counts at list prices; it is not a bill." },
      `${Math.round(spanMs / 1000)} s · $${cost.toFixed(2)} est.`),
  ].filter(Boolean); // replaceChildren would print an empty slot as the word "null"
}
