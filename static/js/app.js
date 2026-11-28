import { callApi, getJson } from "./api.js";
import {
  analystCard, architectCard, boardPlan, boardStats, button, deliveryCard, draftSummary, gateCard, h,
  managerCard, message, objectionsLog, proposal, retryCard, scoreCard, stats, workingCard,
} from "./render.js";
import {
  bidRoundCard, changesSince, decisionMemo, finalProposal, gatesByRound, keyNumbers, loopChips,
  loopStats, meetingPrep, prototypeCard, scoresByRound, trackerList, verdictBanner, whyStopped,
} from "./render-loop.js";
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
  samples: $("sample-row"), modeChip: $("mode-chip"), brandSub: $("brand-sub"),
  relay: $("relay"), summary: $("draft-summary"), proposal: $("proposal"),
  stats: $("team-stats"), notices: $("team-notices"), title: $("team-title"),
  factAgents: $("fact-agents"), factMode: $("fact-mode"),
  boardTitle: $("board-title"), boardIntro: $("board-intro"), boardStats: $("board-stats"),
  boardPlan: $("board-plan"), boardStatus: $("board-status"),
  scoreBlock: $("score-block"), scoreCards: $("score-cards"),
  gateBlock: $("gate-block"), gateCards: $("gate-cards"), objections: $("objections"),
  loopTitle: $("loop-title"), loopStats: $("loop-stats"), loopChips: $("loop-chips"),
  loopRounds: $("loop-rounds"), scoresByRound: $("scores-by-round"), whyStopped: $("why-stopped"),
  trackerList: $("tracker-list"), loopNext: $("loop-next"),
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

// --- Views and stage bar ---

function stageOpen(n) {
  const open = { 1: true, 2: Boolean(run.data), 3: hasDraft(), 4: hasBoard(), 5: hasBoard() && loopStopped() };
  return Boolean(open[n]);
}

function stageDone(n) {
  const done = { 1: Boolean(run.data), 2: hasDraft(), 3: hasBoard(), 4: loopStopped(), 5: hasReport() };
  return Boolean(done[n]);
}

function brandLine(stage) {
  if (stage === 1 || !run.data) return "by Lumen Works";
  const where = { 2: "draft 1", 3: "board round 1", 4: "revisions", 5: "final report" }[stage];
  return `${run.data.case_file.client} · ${where}`;
}

function showView(stage) {
  for (const [n, view] of Object.entries(VIEWS)) view.hidden = Number(n) !== stage;
  for (const step of els.nav.querySelectorAll(".step")) {
    const n = Number(step.dataset.stage);
    step.disabled = !stageOpen(n);
    if (n === stage) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
    step.lastChild.textContent = step.lastChild.textContent.replace(" ✓", "") + (stageDone(n) ? " ✓" : "");
  }
  els.brandSub.textContent = brandLine(stage);
  window.scrollTo({ top: 0 });
}

function setMode(mode) {
  const label = MODE_LABELS[mode] || "Full";
  els.modeChip.hidden = false;
  els.modeChip.textContent = label === "Sample" ? "Sample run" : `${label} mode`;
  els.modeChip.className = `mode-chip ${label.toLowerCase()}`;
  els.factMode.replaceChildren(h("span", { class: "pill-ok" }, label), modeNote(label));
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
  els.stats.replaceChildren(...stats(run.data.steps.filter((s) => s.stage <= 2)));
  els.summary.replaceChildren(...draftSummary(run.data, board));
  els.summary.hidden = false;
  els.proposal.replaceChildren(...proposal(run.data.claims));
  els.proposal.hidden = false;
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
  const checked = gates ? ` and ${countWords(gates, "gatekeeper", "gatekeepers")} checked it` : "";
  return `Code picked the board from the brief. ${countWords(scoring, "executive", "executives")} scored the proposal${checked}, all at the same time. Code turned their answers into votes.`;
}

function setBoardLoading() {
  els.boardTitle.textContent = "The client's board is reviewing draft 1";
  els.boardStats.replaceChildren();
  els.scoreBlock.hidden = true;
  els.gateBlock.hidden = true;
  els.objections.hidden = true;
}

async function board() {
  if (run.busy) return;
  setBusy(true);
  setBoardLoading();
  els.boardPlan.replaceChildren(...boardPlan(run.data.board_plan));
  showView(3);
  const seats = run.data.board_plan.seats.length;
  const working = workingCard(1, `${countWords(seats, "seat is", "seats are")} reviewing draft 1 at the same time.`);
  els.boardStatus.replaceChildren(h("ol", { class: "relay" }, working));
  const result = await callApi("/api/board", stateForServer());
  working.stop();
  setBusy(false);
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
  els.scoreCards.replaceChildren(...scoring.map(card));
  els.gateCards.replaceChildren(...gates.map(card));
  els.scoreBlock.hidden = scoring.length === 0;
  els.gateBlock.hidden = gates.length === 0;
  const next = loopStopped()
    ? { label: "Next: the final report →", onClick: showReport, stopped: true }
    : { label: "Next: the Bid Manager answers the objections →", onClick: startLoop };
  els.objections.replaceChildren(...objectionsLog(run.data.tracker, round.seats, next));
  els.objections.hidden = false;
  showView(3);
}

async function retrySeat(seatId, event) {
  if (run.busy) return;
  const trigger = event.currentTarget;
  trigger.disabled = true;
  trigger.textContent = "Retrying this seat…";
  setBusy(true);
  const result = await callApi("/api/board/retry", { state: stateForServer(), seat_id: seatId });
  setBusy(false);
  if (result.error) {
    trigger.disabled = false;
    trigger.textContent = "Retry this seat";
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
  if (!loopStopped()) return "The Bid Manager is answering the objections";
  if (!rounds) return "Code stopped the loop before a Bid Manager round";
  return `The Bid Manager answered ${answered.size} ${answered.size === 1 ? "objection" : "objections"} in ${rounds} ${rounds === 1 ? "round" : "rounds"}`;
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
  const working = workingCard(roundNo, `Bid Manager round ${roundNo}, then the whole board votes again.`);
  const holder = h("ol", { class: "relay" }, working);
  els.loopRounds.append(holder);
  const result = await callApi("/api/revise", { state: stateForServer(), round_no: roundNo });
  working.stop();
  setBusy(false);
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
  els.reportChanges.replaceChildren(...changesSince(report.changes, report.not_answered || []));
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
  const result = await callApi("/api/report", stateForServer());
  working.stop();
  setBusy(false);
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

async function init() {
  els.brief.addEventListener("input", updateCounter);
  els.start.addEventListener("click", startLive);
  els.newBrief.addEventListener("click", () => showView(1));
  for (const step of els.nav.querySelectorAll(".step")) {
    step.addEventListener("click", () => openStage(Number(step.dataset.stage)));
  }
  showView(1);
  updateCounter();
  const health = await getJson("/api/health");
  if (health) {
    Object.assign(configured, health.models);
    setMode(health.mode);
    els.factAgents.textContent = `${health.agents}, with ${health.tools} tools so far`;
  }
  await loadSamples();
}

init();
