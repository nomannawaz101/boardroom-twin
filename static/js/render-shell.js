// The page shell: stage list states, the Agent activity rail and short model labels. Every value
// shown comes from the step records the server measured; AI text goes in as text nodes.

import { ROLES, WORDS, calculationCount, codeText } from "./labels.js";
import { h, modelTitle, seconds, shortModel } from "./render.js";

const IDLE_AGENTS = ["Business Analyst", "Solution Architect", "Delivery Manager", ROLES.proposal_manager];
export const ACTIVITY_KEY = "boardroom-twin.activity";

export function stageState(n, current, done) {
  if (n === current) return "Now";
  return done ? "Done" : "Next";
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function cost(steps) {
  return steps.reduce((n, s) => n + s.cost_usd, 0);
}

// Seats review at the same time, so their stage time is the span, not the sum.
export function stageSeconds(steps, parallel) {
  if (!steps.length) return 0;
  if (!parallel) return steps.reduce((n, s) => n + s.duration_ms, 0) / 1000;
  const start = Math.min(...steps.map((s) => s.start_ms));
  const end = Math.max(...steps.map((s) => s.start_ms + s.duration_ms));
  return (end - start) / 1000;
}

function stepItem(step) {
  const tools = step.tool_calls.length;
  const model = h("span", { class: "rail-model", title: modelTitle(step) }, shortModel(step));
  const status = step.status === "not_reviewed" ? "Not reviewed" : step.status === "failed" ? "Failed" : "Done";
  return h("li", {},
    h("span", { class: "rail-name" }, codeText(step.label)),
    h("span", { class: "rail-st" }, `${status}, ${seconds(step.duration_ms)}, `, model,
      tools ? `, ${calculationCount(tools)}` : ""));
}

function runningItem(text) {
  const timer = h("span", { class: "num" }, "0 s");
  const started = Date.now();
  const tick = setInterval(() => { timer.textContent = `${Math.round((Date.now() - started) / 1000)} s`; }, 1000);
  const item = h("li", { class: "rail-running", role: "status" },
    h("span", { class: "rail-name" }, text),
    h("span", { class: "rail-st" }, "Running, ", timer, " so far"));
  item.stop = () => clearInterval(tick);
  return item;
}

export function idleRail(facts) {
  return [
    h("section", { class: "rail-block" },
      h("h3", {}, "This run"),
      h("dl", { class: "facts" }, ...facts.flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, value)]))),
    h("section", { class: "rail-block" },
      h("h3", {}, "Agent activity"),
      h("p", { class: "rail-note" }, "Idle. Agents appear here once the run starts."),
      h("ol", { class: "rail-list" }, ...IDLE_AGENTS.map((name) => h("li", {},
        h("span", { class: "rail-name" }, name), h("span", { class: "rail-st" }, "Waiting"))))),
  ];
}

// One stage: each measured step, a running line while a request is out, and the stage total.
export function stageRail(steps, { parallel = false, running = null } = {}) {
  const items = steps.map(stepItem);
  const live = running ? runningItem(running) : null;
  const total = `Stage: ${Math.round(stageSeconds(steps, parallel))} s · about $${cost(steps).toFixed(2)} (estimate from tokens)`;
  const parts = [
    h("section", { class: "rail-block" },
      h("h3", {}, "Agent activity"),
      h("p", { class: "rail-note" }, "Measured while the run happened."),
      h("ol", { class: "rail-list" }, ...items, live),
      steps.length ? h("p", { class: "rail-total num" }, total) : null),
  ];
  parts.stop = () => live && live.stop();
  return parts;
}

export function runSummary(steps) {
  const tokensIn = steps.reduce((n, s) => n + s.tokens_in, 0);
  const tokensOut = steps.reduce((n, s) => n + s.tokens_out, 0);
  const rows = [
    [WORDS.aiSteps, String(steps.length)],
    ["Time", `${Math.round(stageSeconds(steps, false))} s of agent work`],
    [WORDS.tokens, `${tokensIn.toLocaleString("en-US")} in · ${tokensOut.toLocaleString("en-US")} out`],
    ["Cost", `about $${cost(steps).toFixed(2)} (estimate from tokens)`],
  ];
  return [
    h("section", { class: "rail-block" },
      h("h3", {}, "Run summary"),
      h("p", { class: "rail-note" }, "Counted and measured, except cost (estimate from tokens)."),
      h("dl", { class: "facts" }, ...rows.flatMap(([label, value]) => [h("dt", {}, label), h("dd", { class: "num" }, value)]))),
  ];
}

export function railChip(steps, running) {
  if (running) return "Running";
  if (!steps.length) return "Idle";
  return `${plural(steps.length, "step", "steps")} · ${Math.round(stageSeconds(steps, false))} s`;
}

// The toggle is remembered when the browser allows it; a blocked storage keeps the default.
export function readActivity(storage) {
  try {
    return storage.getItem(ACTIVITY_KEY) !== "off";
  } catch {
    return true;
  }
}

export function writeActivity(storage, on) {
  try {
    storage.setItem(ACTIVITY_KEY, on ? "on" : "off");
  } catch {
    // Private mode or storage switched off: the choice lasts for this page only.
  }
}
