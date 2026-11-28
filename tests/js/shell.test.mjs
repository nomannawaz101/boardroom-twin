// The page shell: short model labels, stage states, the Agent activity rail and the remembered
// toggle, rendered by static/js/render-shell.js against the fake DOM.

import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { byClass, holderOf } from "./fake-dom.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const js = (name) => pathToFileURL(path.join(here, "..", "..", "static", "js", name)).href;
const render = await import(js("render.js"));
const shell = await import(js("render-shell.js"));

const step = (fields) => ({
  agent: "a", label: "Business Analyst", tier: "haiku", model: "claude-haiku-5-5", badge: "Haiku",
  start_ms: 0, duration_ms: 3100, tokens_in: 1200, tokens_out: 300, cost_usd: 0.004, tool_calls: [], status: "ok", ...fields,
});

// Model labels: the badge, or the real name cut short; the full name is always in the tooltip.
{
  assert.equal(render.shortModel(step({})), "Haiku");
  const long = step({ badge: "gemini-3.5-flash-preview-0925", model: "models/gemini-3.5-flash-preview-0925", tier: "sonnet" });
  assert.equal(render.shortModel(long), "gemini-3.5-fl…");
  const chip = render.modelChip(long);
  assert.equal(chip.textContent, "gemini-3.5-fl…");
  assert.equal(chip.attrs.title, "Answered by models/gemini-3.5-flash-preview-0925 (sonnet tier)");
}

// Stage list: Done, Now or Next.
{
  assert.equal(shell.stageState(2, 2, true), "Now");
  assert.equal(shell.stageState(1, 2, true), "Done");
  assert.equal(shell.stageState(3, 2, false), "Next");
}

// Idle rail on the Brief: the run facts and the waiting agents.
{
  const text = holderOf(shell.idleRail([["Cost", "≈ $0.16 per run (estimate)"], ["Time", "About 2 to 3 minutes for a full run"]])).textContent;
  assert.match(text, /≈ \$0\.16 per run \(estimate\)/);
  assert.match(text, /About 2 to 3 minutes/);
  assert.match(text, /Idle\. Agents appear here once the run starts\./);
  assert.match(text, /Business AnalystWaiting/);
}

// A stage: measured seconds, short model with tooltip, tool count, cost as an estimate.
{
  const steps = [
    step({}),
    step({ label: "Delivery Manager", start_ms: 3100, duration_ms: 6200, cost_usd: 0.012, tool_calls: [{}, {}], badge: "Sonnet", tier: "sonnet" }),
  ];
  const holder = holderOf(shell.stageRail(steps));
  assert.match(holder.textContent, /Business AnalystDone, 3\.1 s, Haiku/);
  assert.match(holder.textContent, /Delivery ManagerDone, 6\.2 s, Sonnet, 2 code calculations/);
  assert.match(holder.textContent, /Stage: 9 s · about \$0\.02 \(estimate from tokens\)/);
  assert.equal(byClass(holder, "rail-model")[1].attrs.title, "Answered by claude-haiku-5-5 (sonnet tier)");
  // Seats run at the same time: the stage time is the span, not the sum.
  const seats = [step({ start_ms: 100, duration_ms: 8000 }), step({ start_ms: 120, duration_ms: 9000 })];
  assert.match(holderOf(shell.stageRail(seats, { parallel: true })).textContent, /Stage: 9 s/);
  const running = shell.stageRail([], { running: "Bid Manager, round 1, then the board" });
  assert.match(holderOf(running).textContent, /Bid Manager, round 1, then the boardRunning, 0 s so far/);
  running.stop();
  assert.equal(shell.railChip([], "x"), "Running");
  assert.equal(shell.railChip([], null), "Idle");
  assert.equal(shell.railChip(steps, null), "2 steps · 9 s");
}

// Run summary on the Report: counted values and the cost marked as an estimate.
{
  const text = holderOf(shell.runSummary([step({}), step({ duration_ms: 1900 })])).textContent;
  assert.match(text, /AI steps2/);
  assert.match(text, /5 s of agent work/);
  assert.match(text, /2,400 in · 600 out/);
  assert.match(text, /about \$0\.01 \(estimate from tokens\)/);
}

// The toggle is remembered, and storage that throws never breaks the page.
{
  const store = new Map();
  const ok = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  assert.equal(shell.readActivity(ok), true); // on by default
  shell.writeActivity(ok, false);
  assert.equal(store.get(shell.ACTIVITY_KEY), "off");
  assert.equal(shell.readActivity(ok), false);
  const blocked = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); } };
  assert.equal(shell.readActivity(blocked), true);
  shell.writeActivity(blocked, false);
  assert.equal(shell.readActivity(null), true);
}

process.stdout.write("shell: all checks passed\n");
