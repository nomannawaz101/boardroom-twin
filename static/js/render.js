// Builds every card from step records and responses. All AI text goes in as text nodes;
// no HTML string is ever parsed (guard G12).

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

function seconds(ms) {
  return `${(ms / 1000).toFixed(1)} s`;
}

function yesNo(value) {
  return value === true ? "yes" : value === false ? "no" : "unclear";
}

// --- Small parts ---

export function modelChip(tier) {
  return tier === "haiku" ? h("span", { class: "m-haiku" }, "Haiku") : h("span", { class: "m-sonnet" }, "Sonnet");
}

function codeChip() {
  return h("span", { class: "m-code" }, "Code, no AI");
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

function agentCard(index, step, body, last) {
  const tools = step.tool_calls.length;
  const time = tools ? `${seconds(step.duration_ms)} · ${tools} ${tools === 1 ? "tool" : "tools"}` : seconds(step.duration_ms);
  const card = h(
    "div", { class: "card agent-card" },
    h("div", { class: "agent-head" },
      h("strong", {}, step.label), modelChip(step.tier), h("span", { class: "num agent-time" }, time)),
    h("span", { class: "agent-summary" }, step.summary),
    ...body,
    flagNotes(step),
    handLine(step.handoff_out),
  );
  return h("li", { "data-agent": step.agent }, rail(index, last), card);
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

function flagChip(label, value) {
  return h("span", { class: "flag" }, h("b", {}, `${label}:`), ` ${value}`);
}

function boardStrip(plan) {
  const seats = plan.seats.map((s) => h("span", { class: "seat", title: s.why }, s.title));
  const skipped = plan.skipped.map((s) => h("span", { class: "seat skipped", title: s.why_not }, `${s.title} (not needed)`));
  return h("div", { class: "chips" }, h("span", { class: "chips-label" }, "Board for this brief"), codeChip(), ...seats, ...skipped);
}

function inputChecks(checks) {
  const injection = checks.injection === "notice" ? "instruction-like text kept as data" : "no hidden instructions";
  return h(
    "div", { class: "tool" },
    h("span", { class: "tname" }, "Input checks"), codeChip(),
    h("span", { class: "ok-text" }, `No real personal data · ${injection} · looks like a client brief`),
  );
}

export function analystCard(data, last) {
  const step = data.steps.find((s) => s.agent === "business_analyst");
  const caseFile = data.case_file;
  const flags = data.flags;
  const signals = h(
    "div", { class: "chips" },
    ...caseFile.goals.map((g) => h("span", { class: "chip-goal" }, `Goal: ${g}`)),
    ...caseFile.warnings.map((w) => h("span", { class: "chip-warn", title: `"${w.quote}"` }, `Warning: ${w.text}`)),
  );
  const flagRow = h(
    "div", { class: "chips" },
    h("span", { class: "chips-label" }, "Context flags"),
    flagChip("Personal data", yesNo(flags.personal_data)),
    flagChip("Existing systems", yesNo(flags.existing_systems)),
    flagChip("Contract", CONTRACT[flags.contract_type] || "unclear"),
    flagChip("Function", flags.function || "unclear"),
    flagChip("Level", LEVEL[flags.seniority] || "unclear"),
  );
  return agentCard(1, step, [signals, flagRow, inputChecks(data.checks), boardStrip(data.board_plan)], last);
}

// --- Stage 2: Solution Architect, Delivery Manager, Proposal Manager ---

export function architectCard(index, step, design, last) {
  const parts = h("div", { class: "parts" },
    ...design.parts.map((p) => h("div", { class: "part" }, h("strong", {}, p.name), h("span", {}, p.purpose))));
  return agentCard(index, step, [parts], last);
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
  return agentCard(index, step, body, last);
}

export function managerCard(index, step, last) {
  return agentCard(index, step, [], last);
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

function teamText(efforts) {
  if (!efforts || !efforts.length) return "To confirm";
  const engineers = Math.max(...efforts.map((e) => e.engineers));
  const weeks = efforts.reduce((sum, e) => sum + e.weeks, 0);
  return `${engineers} ${engineers === 1 ? "engineer" : "engineers"}, ${weeks} weeks`;
}

export function draftSummary(data) {
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
      h("span", { class: "muted small" }, `9 sections · ${data.claims.length} claims`)),
    h("strong", { class: "draft-title" }, `Proposal for ${data.case_file.client}`),
    h("dl", { class: "draft-facts" },
      ...facts.flatMap(([label, value, mono]) => [h("dt", {}, label), h("dd", { class: mono ? "num" : null }, value)])),
    h("ol", { class: "section-list" }, ...Object.values(SECTION_TITLES).map((t) => h("li", {}, t))),
    button("Next: send it to the client board →", "btn btn-primary", null, true),
    h("span", { class: "muted small tight" }, "The client board arrives in the next build."),
  ];
}

function tagFor(origin) {
  const tag = TAGS[origin];
  return tag ? h("span", { class: `tag ${tag[1]}` }, tag[0]) : null;
}

export function proposal(claims) {
  const legend = h("div", { class: "legend" }, "Tags:",
    ...Object.values(TAGS).map(([text, cls]) => h("span", { class: `tag ${cls}` }, text)),
    "Recommendations carry no tag.");
  const sections = Object.entries(SECTION_TITLES).map(([id, title], i) => {
    const items = claims.filter((c) => c.section === id);
    const list = items.length
      ? h("ul", {}, ...items.map((c) => h("li", {}, h("span", { class: "num claim-id" }, c.id), c.text, " ", tagFor(c.origin))))
      : h("span", { class: "empty-sec" }, "Nothing yet.");
    return h("div", { class: "sec" }, h("h3", {}, `${i + 1}. ${title}`), list);
  });
  return [h("h2", { id: "proposal-h" }, "Proposal, draft 1"), legend, ...sections];
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
