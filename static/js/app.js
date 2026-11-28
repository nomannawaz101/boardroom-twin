import { callApi, getJson } from "./api.js";
import {
  analystCard, architectCard, boardPlan, fixFirst, ranTogether, togetherMarker, verdictSoFar, boardStats, button, deliveryCard, draftSummary, gateCard, h,
  managerCard, message, objectionsLog, proposal, retryCard, scoreCard, stats, workingCard,
} from "./render.js";
import {
  bidRoundCard, changesSince, decisionMemo, finalProposal, gatesByRound, keyNumbers, loopChips,
  loopStats, meetingPrep, objectionsTable, prototypeCard, scoresByRound, trackerList, verdictBanner, whyStopped,
} from "./render-loop.js";
import { MODES, PAGE_TEXT, ROLES, WORDS, reviewerCount } from "./labels.js";
import {
  idleRail, railChip, readActivity, runSummary, stageRail, stageState, writeActivity,
} from "./render-shell.js";
import {
  BRIEF_MAX_CHARS, addBoard, addDraft, addRetriedSeat, addRevision, hasBoard, hasDraft, hasReport,
  loopStopped, run, setReport, startRun, stateForServer,
} from "./state.js";

// Errors the user fixes by changing the brief, so they are shown on the brief screen.
const INPUT_ERRORS = new Set(["input_blocked", "too_long", "not_a_brief"]);
const ERROR_TITLES = {
  input_blocked: "Check the brief.",
  too_long: "Too long.",
  not_a_brief: "This doesn't look like a client brief.",
};
const MODE_LABELS = { auto: "Full", full: "Full", lite: "Lite", sample: "Sample" };
// Filled from /api/health: the badges of the configured models, never assumed.
const configured = { main: "", fast: "" };

function modeNote(label) {
  if (label === "Sample") return "Recorded run";
  if (!configured.main) return "";
  if (label === "Lite" || configured.main === configured.fast) return `${configured.fast} only`;
  return `${configured.main} and ${configured.fast}`;
}

const $ = (id) => document.getElementById(id);
const els = {
  nav: $("stage-nav"),
  client: $("client"), country: $("country"), brief: $("brief"), counter: $("brief-counter"),
  confirmed: $("confirmed"), start: $("start-live"), startMessage: $("start-message"),
  samples: $("sample-row"), modeChip: $("mode-chip"), clientChip: $("client-chip"),
  toggle: $("activity-toggle"), railDetails: $("rail-details"), railBody: $("rail-body"), railChip: $("rail-chip"),
  relay: $("relay"), summary: $("draft-summary"), proposal: $("proposal"), proposalDetails: $("proposal-details"),
  stats: $("team-stats"), notices: $("team-notices"), title: $("team-title"),
  boardTitle: $("board-title"), boardIntro: $("board-intro"), boardStats: $("board-stats"),
  boardPlan: $("board-plan"), boardStatus: $("board-status"),
  scoreBlock: $("score-block"), scoreCards: $("score-cards"),
  gateBlock: $("gate-block"), gateCards: $("gate-cards"), objections: $("objections"),
  boardVerdict: $("board-verdict"), fixFirst: $("fix-first"), boardNext: $("board-next"),
  loopTitle: $("loop-title"), loopStats: $("loop-stats"), loopChips: $("loop-chips"),
  loopRounds: $("loop-rounds"), scoresByRound: $("scores-by-round"), whyStopped: $("why-stopped"),
  trackerList: $("tracker-list"), loopNext: $("loop-next"), loopObjections: $("loop-objections"),
  reportStatus: $("report-status"), reportBody: $("report-body"), verdictBanner: $("verdict-banner"),
  keyNumbers: $("key-numbers"), reportChanges: $("report-changes"), reportProposal: $("report-proposal"),
  reportMemo: $("report-memo"), reportPrep: $("report-prep"), reportPrototype: $("report-prototype"),
  newBrief: $("new-brief"),
};
const VIEWS = {
  1: $("view-brief"), 2: $("view-team"), 3: $("view-board"), 4: $("view-revisions"), 5: $("view-report"),
};
// Steps made before the loop started, so the loop's own calls can be counted.
let loopStart = 0;
let currentStage = 1;
// The Brief screen's "This run" facts: placeholders until /api/health answers.
const facts = { agents: "14", mode: null };
let railParts = [];
const NARROW = "(max-width: 1100px)";

// --- Views and stage bar ---

function stageOpen(n) {
  const open = { 1: true, 2: Boolean(run.data), 3: hasDraft(), 4: hasBoard(), 5: hasBoard() && loopStopped() };
  return Boolean(open[n]);
}

function stageDone(n) {
  const done = { 1: Boolean(run.data), 2: hasDraft(), 3: hasBoard(), 4: loopStopped(), 5: hasReport() };
  return Boolean(done[n]);
}

function clientLine(stage) {
  if (!run.data) return "";
  const where = { 1: "", 2: "draft 1", 3: "board round 1", 4: "revisions", 5: "final report" }[stage];
  return where ? `${run.data.case_file.client} · ${where}` : run.data.case_file.client;
}

function showView(stage) {
  currentStage = stage;
  for (const [n, view] of Object.entries(VIEWS)) view.hidden = Number(n) !== stage;
  for (const step of els.nav.querySelectorAll(".step")) {
    const n = Number(step.dataset.stage);
    step.disabled = !stageOpen(n);
    step.classList.toggle("done", stageDone(n));
    if (n === stage) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
    step.querySelector(".step-state").textContent = stageState(n, stage, stageDone(n));
  }
  els.clientChip.textContent = clientLine(stage);
  els.clientChip.hidden = !run.data;
  renderRail();
  window.scrollTo({ top: 0 });
}

// --- Agent activity rail ---

function factRows() {
  const mode = facts.mode || "Full";
  return [
    ["Agent roles", facts.agents],
    ["Board", "3 to 5 reviewers, chosen from your brief"],
    ["Time", "About 2 to 3 minutes for a full run"],
    ["Cost", "≈ $0.16 per run (estimate)"],
    ["Mode", h("span", {}, h("span", { class: "pill-ok" }, MODES[mode] || mode), modeNote(mode))],
  ];
}

function railSteps(stage) {
  const steps = run.data ? run.data.steps : [];
  if (stage === 2) return steps.filter((s) => s.stage <= 2);
  if (stage === 3) return steps.filter((s) => s.stage === 3);
  if (stage === 4) {
    // Name each Bid Manager call by its round; the seats after it are that round's vote.
    let round = 0;
    return steps.slice(loopStart).map((s) => {
      if (s.agent !== "bid_manager") return { ...s, label: round ? `${s.label}, vote ${round + 1}` : s.label };
      round += 1;
      return { ...s, label: `${s.label}, round ${round}` };
    });
  }
  return steps;
}

// Redrawn on every view change and around every request; `running` names the work in progress.
function renderRail(running = null) {
  if (railParts.stop) railParts.stop();
  const stage = currentStage;
  const steps = railSteps(stage);
  if (stage === 1 || !run.data) railParts = idleRail(factRows());
  else if (stage === 5 && hasReport() && !running) railParts = runSummary(steps);
  else railParts = stageRail(stage === 5 ? [] : steps, { parallel: stage === 3, running });
  els.railBody.replaceChildren(...railParts);
  els.railChip.textContent = railChip(stage === 1 ? [] : steps, running);
}

function storage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function setActivity(on) {
  document.body.classList.toggle("rail-off", !on);
  els.toggle.textContent = `Agent activity: ${on ? "On" : "Off"}`;
  els.toggle.setAttribute("aria-pressed", String(on));
}

function fitRail() {
  els.railDetails.open = !window.matchMedia(NARROW).matches;
}

function setMode(mode) {
  const label = MODE_LABELS[mode] || "Full";
  els.modeChip.hidden = false;
  els.modeChip.textContent = MODES[label] || label;
  els.modeChip.className = `mode-chip ${label.toLowerCase()}`;
  facts.mode = label;
  renderRail();
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
  els.proposalDetails.hidden = true;
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
  renderRail("Business Analyst");
  const result = await callApi("/api/discover", body);
  working.stop();
  setBusy(false);
  renderRail();
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
  els.relay.replaceChildren(analystCard(run.data));
  showView(2);
  await draft();
}

// --- Stage 2: draft ---

async function draft() {
  setBusy(true);
  const working = workingCard(2, `Solution Architect, then Delivery Manager, then ${ROLES.proposal_manager} are working. This takes about a minute.`);
  els.relay.append(working);
  renderRail(`Solution Architect, Delivery Manager, ${ROLES.proposal_manager}`);
  const result = await callApi("/api/draft", stateForServer());
  working.stop();
  working.remove();
  setBusy(false);
  renderRail();
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
  const cards = [
    architectCard(2, architect, result.design),
    deliveryCard(3, delivery, run.data),
    managerCard(4, manager),
  ];
  // Mark steps whose measured times overlap; today's chain runs one after another.
  result.steps.forEach((step, i) => {
    if (i && ranTogether(result.steps[i - 1], step)) els.relay.append(togetherMarker());
    els.relay.append(cards[i]);
  });
  els.title.textContent = "The proposal team wrote draft 1";
  els.stats.replaceChildren(...stats(run.data.steps.filter((s) => s.stage <= 2)));
  els.summary.replaceChildren(...draftSummary(run.data, board));
  els.summary.hidden = false;
  els.proposal.replaceChildren(...proposal(run.data.claims));
  els.proposal.hidden = false;
  els.proposalDetails.hidden = false;
  showView(2);
}

// --- Stage 3: the client board ---

function boardSteps() {
  return run.data.steps.filter((s) => s.stage === 3);
}

function countWords(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function boardIntro(round) {
  const scoring = round.seats.filter((s) => s.kind === "scoring").length;
  const gates = round.seats.length - scoring;
  const checked = gates ? ` and ${countWords(gates, WORDS.signOffReviewer, WORDS.signOffReviewers)} checked it` : "";
  return `Fixed rules picked the board from the brief. ${countWords(scoring, "executive", "executives")} scored the proposal${checked}, all at the same time. Fixed rules turned their answers into votes.`;
}

function setBoardLoading() {
  els.boardTitle.textContent = "The client's board is reviewing draft 1";
  els.boardStats.replaceChildren();
  els.scoreBlock.hidden = true;
  els.gateBlock.hidden = true;
  els.objections.hidden = true;
  els.boardVerdict.replaceChildren();
  els.fixFirst.hidden = true;
  els.boardNext.replaceChildren();
}

async function board() {
  if (run.busy) return;
  setBusy(true);
  setBoardLoading();
  els.boardPlan.replaceChildren(...boardPlan(run.data.board_plan));
  showView(3);
  const seats = run.data.board_plan.seats.length;
  const working = workingCard(1, `${countWords(seats, "reviewer is", "reviewers are")} reviewing draft 1 at the same time.`);
  els.boardStatus.replaceChildren(h("ol", { class: "relay" }, working));
  renderRail(`${reviewerCount(seats)}, at the same time`);
  const result = await callApi("/api/board", stateForServer());
  working.stop();
  setBusy(false);
  renderRail();
  if (result.error) {
    els.boardStatus.replaceChildren(h("ol", { class: "relay" }, retryCard(1, result.message, board, () => showView(2))));
    return;
  }
  addBoard(result);
  showBoard();
}

function showBoard() {
  const round = run.data.rounds.at(-1);
  const steps = Object.fromEntries(boardSteps().map((s) => [s.agent, s]));
  const card = (seat) => (seat.kind === "scoring" ? scoreCard : gateCard)(seat, steps[seat.seat_id], (event) => retrySeat(seat.seat_id, event));
  const scoring = round.seats.filter((s) => s.kind === "scoring");
  const gates = round.seats.filter((s) => s.kind === "gate");
  els.boardStatus.replaceChildren();
  els.boardTitle.textContent = "The client's board reviewed draft 1";
  els.boardIntro.textContent = boardIntro(round);
  els.boardStats.replaceChildren(...boardStats(boardSteps(), round.progress, run.data.verdictLabel));
  els.boardVerdict.replaceChildren(run.data.verdictLabel ? verdictSoFar(run.data.verdictLabel, round.progress) : "");
  els.boardPlan.replaceChildren(...boardPlan(run.data.board_plan, round));
  els.scoreCards.replaceChildren(...scoring.map(card));
  els.gateCards.replaceChildren(...gates.map(card));
  els.scoreBlock.hidden = scoring.length === 0;
  els.gateBlock.hidden = gates.length === 0;
  const next = loopStopped()
    ? { label: "Next: the final report →", onClick: showReport, stopped: true }
    : { label: `Next: the ${ROLES.bid_manager} answers the objections →`, onClick: startLoop };
  els.objections.replaceChildren(...objectionsLog(run.data.tracker, round.seats, { stopped: next.stopped }));
  els.objections.hidden = false;
  const fix = fixFirst(run.data.tracker, round.seats);
  els.fixFirst.replaceChildren(...fix);
  els.fixFirst.hidden = !fix.length;
  els.boardNext.replaceChildren(button(next.label, "btn btn-primary", next.onClick));
  showView(3);
}

async function retrySeat(seatId, event) {
  if (run.busy) return;
  const trigger = event.currentTarget;
  trigger.disabled = true;
  trigger.textContent = WORDS.retryingReviewer;
  setBusy(true);
  const result = await callApi("/api/board/retry", { state: stateForServer(), seat_id: seatId });
  setBusy(false);
  if (result.error) {
    trigger.disabled = false;
    trigger.textContent = WORDS.retryReviewer;
    trigger.after(message("m-err", null, result.message));
    return;
  }
  addRetriedSeat(result);
  showBoard();
}

// --- Stage 4: the revision loop, one Bid Manager round per request ---

function loopSteps() {
  return run.data.steps.slice(loopStart);
}

function bidSteps() {
  return run.data.steps.filter((s) => s.agent === "bid_manager");
}

function loopTitle() {
  const answered = new Set(run.data.revisions.flatMap((r) => r.answered));
  const rounds = run.data.revisions.length;
  if (!loopStopped()) return `The ${ROLES.bid_manager} is answering the objections`;
  if (!rounds) return `Fixed rules stopped the loop before a ${ROLES.bid_manager} round`;
  return `The ${ROLES.bid_manager} answered ${answered.size} ${answered.size === 1 ? "objection" : "objections"} in ${rounds} ${rounds === 1 ? "round" : "rounds"}`;
}

function renderLoop(running) {
  const { rounds, revisions, tracker, stop } = run.data;
  const steps = bidSteps();
  els.loopTitle.textContent = loopTitle();
  els.loopStats.replaceChildren(...loopStats(loopSteps()));
  els.loopChips.replaceChildren(...loopChips(rounds, stop, running));
  els.loopRounds.replaceChildren(...revisions.map((rev, i) =>
    bidRoundCard(rev, steps[i], rounds[i], rounds[i + 1], tracker, loopStopped() && i === revisions.length - 1)));
  els.scoresByRound.replaceChildren(...scoresByRound(rounds), ...gatesByRound(rounds));
  els.whyStopped.replaceChildren(...whyStopped(stop));
  els.trackerList.replaceChildren(...trackerList(tracker));
  els.loopObjections.replaceChildren(...objectionsTable(tracker, rounds[0].seats, revisions));
  els.loopNext.replaceChildren(loopStopped() ? button("Next: the final report →", "btn btn-primary wide-btn", showReport) : "");
}

async function startLoop() {
  if (run.busy) return;
  loopStart = run.data.steps.length;
  showView(4);
  renderLoop(true);
  await nextRound();
}

async function nextRound() {
  if (loopStopped()) {
    renderLoop(false);
    showView(4);
    return;
  }
  setBusy(true);
  const roundNo = run.data.revisions.length + 1;
  const working = workingCard(roundNo, `${ROLES.bid_manager} round ${roundNo}, then the whole board votes again.`);
  const holder = h("ol", { class: "relay" }, working);
  els.loopRounds.append(holder);
  renderRail(`${ROLES.bid_manager}, round ${roundNo}, then the board`);
  const result = await callApi("/api/revise", { state: stateForServer(), round_no: roundNo });
  working.stop();
  setBusy(false);
  renderRail();
  if (result.error) {
    els.loopChips.replaceChildren(...loopChips(run.data.rounds, run.data.stop, false));
    holder.replaceChildren(retryCard(roundNo, result.message, () => { holder.remove(); nextRound(); }, () => showView(3)));
    return;
  }
  addRevision(result);
  renderLoop(!loopStopped());
  showView(4);
  if (!loopStopped()) await nextRound();
}

// --- Stage 5: the final report ---

function downloadRun() {
  const payload = { ...stateForServer(), report: run.data.report };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = h("a", { href: url, download: `boardroom-twin-run-${run.data.run_id}.json` });
  document.body.append(link); // some browsers ignore a click on a link that is not on the page
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderReport() {
  const report = run.data.report;
  els.verdictBanner.replaceChildren(verdictBanner(report, () => window.print(), downloadRun));
  els.keyNumbers.replaceChildren(...keyNumbers(report.numbers));
  els.reportChanges.replaceChildren(...changesSince(report.changes, report.not_answered || [], run.data.tracker));
  els.reportProposal.replaceChildren(...finalProposal(run.data.claims, run.data.draft_no, run.data.case_file.client));
  els.reportMemo.replaceChildren(...decisionMemo(report.memo));
  els.reportPrep.replaceChildren(...meetingPrep(report.confirm_with_client, report.decisions || []));
  els.reportPrototype.replaceChildren(...prototypeCard());
  els.reportBody.hidden = false;
}

async function showReport() {
  if (run.busy) return;
  showView(5);
  if (hasReport()) {
    renderReport();
    return;
  }
  setBusy(true);
  els.reportBody.hidden = true;
  const working = workingCard(1, "Code is assembling the final report.");
  els.reportStatus.replaceChildren(h("ol", { class: "relay" }, working));
  renderRail("Code assembles the report");
  const result = await callApi("/api/report", stateForServer());
  working.stop();
  setBusy(false);
  renderRail();
  if (result.error) {
    els.reportStatus.replaceChildren(h("ol", { class: "relay" }, retryCard(1, result.message, showReport, () => showView(4))));
    return;
  }
  els.reportStatus.replaceChildren();
  setReport(result.report);
  renderReport();
  showView(5);
}

// --- Start up ---

function openStage(n) {
  if (n === 4) renderLoop(false);
  if (n === 5 && hasReport()) renderReport();
  showView(n);
}

// Static page texts come from the labels file too, so a rename is one edit.
function applyPageText() {
  for (const node of document.querySelectorAll("[data-text]")) {
    if (PAGE_TEXT[node.dataset.text]) node.textContent = PAGE_TEXT[node.dataset.text];
  }
}

async function init() {
  applyPageText();
  els.brief.addEventListener("input", updateCounter);
  els.start.addEventListener("click", startLive);
  $("start-with-brief").addEventListener("click", () => {
    $("brief-card").scrollIntoView({ behavior: "smooth", block: "start" });
    els.brief.focus({ preventScroll: true });
  });
  els.newBrief.addEventListener("click", () => showView(1));
  for (const step of els.nav.querySelectorAll(".step")) {
    step.addEventListener("click", () => openStage(Number(step.dataset.stage)));
  }
  setActivity(readActivity(storage()));
  els.toggle.addEventListener("click", () => {
    const on = document.body.classList.contains("rail-off");
    setActivity(on);
    writeActivity(storage(), on);
  });
  fitRail();
  window.matchMedia(NARROW).addEventListener("change", fitRail);
  showView(1);
  updateCounter();
  const health = await getJson("/api/health");
  if (health) {
    Object.assign(configured, health.models);
    setMode(health.mode);
    facts.agents = `${health.agents}, with ${health.tools} tools so far`;
    renderRail();
  }
  await loadSamples();
}

init();
