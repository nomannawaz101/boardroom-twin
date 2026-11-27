import { callApi, getJson } from "./api.js";
import {
  analystCard, architectCard, deliveryCard, draftSummary, h, managerCard, message, proposal,
  retryCard, stats, workingCard,
} from "./render.js";
import { BRIEF_MAX_CHARS, addDraft, hasDraft, run, startRun, stateForServer } from "./state.js";

// Errors the user fixes by changing the brief, so they are shown on the brief screen.
const INPUT_ERRORS = new Set(["input_blocked", "too_long", "not_a_brief"]);
const ERROR_TITLES = {
  input_blocked: "Check the brief.",
  too_long: "Too long.",
  not_a_brief: "This doesn't look like a client brief.",
};
const MODE_LABELS = { auto: "Full", full: "Full", lite: "Lite", sample: "Sample" };
const MODE_NOTES = { Full: "Sonnet and Haiku", Lite: "Haiku only", Sample: "Recorded run" };

const $ = (id) => document.getElementById(id);
const els = {
  viewBrief: $("view-brief"), viewTeam: $("view-team"), nav: $("stage-nav"),
  client: $("client"), country: $("country"), brief: $("brief"), counter: $("brief-counter"),
  confirmed: $("confirmed"), start: $("start-live"), startMessage: $("start-message"),
  samples: $("sample-row"), modeChip: $("mode-chip"), brandSub: $("brand-sub"),
  relay: $("relay"), summary: $("draft-summary"), proposal: $("proposal"),
  stats: $("team-stats"), notices: $("team-notices"), title: $("team-title"),
  factAgents: $("fact-agents"), factMode: $("fact-mode"),
};

// --- Views and stage bar ---

function showView(stage) {
  els.viewBrief.hidden = stage !== 1;
  els.viewTeam.hidden = stage !== 2;
  for (const step of els.nav.querySelectorAll(".step")) {
    const n = Number(step.dataset.stage);
    const done = (n === 1 && run.data) || (n === 2 && hasDraft());
    step.disabled = !(n === 1 || (n === 2 && run.data));
    if (n === stage) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
    step.lastChild.textContent = step.lastChild.textContent.replace(" ✓", "") + (done ? " ✓" : "");
  }
  els.brandSub.textContent = stage === 1 || !run.data ? "by Lumen Works" : `${run.data.case_file.client} · draft 1`;
  window.scrollTo({ top: 0 });
}

function setMode(mode) {
  const label = MODE_LABELS[mode] || "Full";
  els.modeChip.hidden = false;
  els.modeChip.textContent = label === "Sample" ? "Sample run" : `${label} mode`;
  els.modeChip.className = `mode-chip ${label.toLowerCase()}`;
  els.factMode.replaceChildren(h("span", { class: "pill-ok" }, label), MODE_NOTES[label]);
}

// --- Brief form ---

function updateCounter() {
  const length = els.brief.value.length;
  els.counter.textContent = `${length.toLocaleString("en-US")} / ${BRIEF_MAX_CHARS.toLocaleString("en-US")} characters`;
  els.counter.classList.toggle("over", length > BRIEF_MAX_CHARS);
}

function pickSample(sample, buttonNode) {
  els.client.value = sample.client;
  els.country.value = sample.country;
  els.brief.value = sample.brief;
  for (const b of els.samples.querySelectorAll(".sample")) b.setAttribute("aria-pressed", String(b === buttonNode));
  updateCounter();
}

async function loadSamples() {
  const samples = (await getJson("/static/sample/briefs.json")) || [];
  for (const sample of samples) {
    const node = h("button", { type: "button", class: "sample", "aria-pressed": "false" }, sample.title, h("small", {}, sample.subtitle));
    node.addEventListener("click", () => pickSample(sample, node));
    els.samples.append(node);
  }
  if (samples.length) pickSample(samples[0], els.samples.firstChild);
}

function showStartMessage(node) {
  els.startMessage.replaceChildren(node || "");
}

function formBody() {
  return {
    client: els.client.value,
    country: els.country.value,
    brief: els.brief.value,
    confirmed_fake: els.confirmed.checked,
  };
}

function precheck(body) {
  if (!body.confirmed_fake) return "Please confirm the data is made up or public.";
  if (!body.brief.trim()) return "Please paste a client brief.";
  if (body.brief.length > BRIEF_MAX_CHARS) return `The brief is over ${BRIEF_MAX_CHARS.toLocaleString("en-US")} characters. Please shorten it.`;
  return null;
}

// --- Stage 1: discover ---

function setBusy(busy) {
  run.busy = busy;
  els.start.disabled = busy;
}

async function startLive() {
  if (run.busy) return;
  const body = formBody();
  const problem = precheck(body);
  if (problem) {
    showStartMessage(message("m-err", null, problem));
    return;
  }
  showStartMessage(null);
  run.data = null;
  els.relay.replaceChildren();
  els.summary.hidden = true;
  els.proposal.hidden = true;
  els.stats.replaceChildren();
  els.notices.replaceChildren();
  els.title.textContent = "The proposal team is writing draft 1";
  showView(2);
  await discover(body);
}

async function discover(body) {
  setBusy(true);
  const working = workingCard(1, "Business Analyst is reading the brief. Code checked it first.");
  els.relay.replaceChildren(working);
  const result = await callApi("/api/discover", body);
  working.stop();
  setBusy(false);
  if (result.error && INPUT_ERRORS.has(result.error)) {
    showView(1);
    showStartMessage(message("m-err", ERROR_TITLES[result.error], result.message));
    return;
  }
  if (result.error) {
    els.relay.replaceChildren(retryCard(1, result.message, () => discover(body), () => showView(1)));
    return;
  }
  startRun(result);
  setMode(result.mode);
  els.notices.replaceChildren(...result.notices.map((n) => message("m-warn", "Instructions aimed at an AI.", n)));
  els.relay.replaceChildren(analystCard(run.data, false));
  showView(2);
  await draft();
}

// --- Stage 2: draft ---

async function draft() {
  setBusy(true);
  const working = workingCard(2, "Solution Architect, then Delivery Manager, then Proposal Manager are working. This takes about a minute.");
  els.relay.append(working);
  const result = await callApi("/api/draft", stateForServer());
  working.stop();
  working.remove();
  setBusy(false);
  if (result.error) {
    els.relay.append(retryCard(2, result.message, () => {
      els.relay.lastChild.remove();
      draft();
    }, () => showView(1)));
    return;
  }
  addDraft(result);
  showDraft(result);
}

function showDraft(result) {
  const [architect, delivery, manager] = result.steps;
  els.relay.append(
    architectCard(2, architect, result.design, false),
    deliveryCard(3, delivery, run.data, false),
    managerCard(4, manager, true),
  );
  els.title.textContent = "The proposal team wrote draft 1";
  els.stats.replaceChildren(...stats(run.data.steps));
  els.summary.replaceChildren(...draftSummary(run.data));
  els.summary.hidden = false;
  els.proposal.replaceChildren(...proposal(run.data.claims));
  els.proposal.hidden = false;
  showView(2);
}

// --- Start up ---

async function init() {
  els.brief.addEventListener("input", updateCounter);
  els.start.addEventListener("click", startLive);
  for (const step of els.nav.querySelectorAll(".step")) {
    step.addEventListener("click", () => showView(Number(step.dataset.stage)));
  }
  showView(1);
  updateCounter();
  const health = await getJson("/api/health");
  if (health) {
    setMode(health.mode);
    els.factAgents.textContent = `${health.agents}, with ${health.tools} tools so far`;
  }
  await loadSamples();
}

init();
