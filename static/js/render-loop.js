// Stages 4 and 5: the revision loop and the final report. Built from server responses; all AI
// text goes in as text nodes (guard G12). Every number shown was computed by code.

import {
  button, decisionPill, decisionText, h, handLine, modelChip, proposal, scoreText, seconds,
} from "./render.js";
import {
  CHANGE_TEXT_MAX, SCORES_MOVE, WEEKDAYS, OUTCOMES, ROLES, WORDS as W, trimmed, STATUS, WORDS, codeText, objectionId, reviewerCount, statementId,
} from "./labels.js";

const GATE_CLASSES = { pass: "pill-good", pass_with_conditions: "pill-cond", blocked: "pill-bad" };
const VERDICT_CLASSES = {
  approved: "verdict-good", approved_with_conditions: "verdict-good",
  review_incomplete: "verdict-warn", not_ready: "verdict-bad",
};
const ACTION_WORDS = { replace: "Changed", remove: "Removed", add: "Added", assume: "Assumption" };
const REFUSAL_WORDS = {
  locked: "a calculated statement is locked",
  unknown_claim: "no such statement",
  unknown_objection: "no open objection with that id",
  empty: "no text",
  client_only: "only the client can settle this, so it can only be an assumption",
  protected: "commercial facts, dates and brief statements can only change through an assumption",
  duplicate: "the same assumption is already in the proposal",
};

function notAnsweredRow(id) {
  return h("div", { class: "change refused" },
    h("span", { class: "num change-id" }, objectionId(id)),
    h("span", { class: "muted" }, `Not answered by the ${ROLES.bid_manager}.`));
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

// --- Loop chips: "Board round 1: 2 of 5 can proceed" → … → "Stopped by code" ---

export function loopChips(rounds, stop, running) {
  const chips = [];
  rounds.forEach((round, i) => {
    const text = i === 0
      ? `Board round 1: ${round.progress.able} of ${reviewerCount(round.progress.total)} can approve`
      : `Revision round ${i} → Board round ${round.no}: ${round.progress.able} of ${round.progress.total}`;
    if (i) chips.push(h("span", { class: "loop-arrow", "aria-hidden": "true" }, "→"));
    chips.push(h("span", { class: "loop-chip" }, text));
  });
  chips.push(h("span", { class: "loop-arrow", "aria-hidden": "true" }, "→"));
  chips.push(stop && stop.stopped
    ? h("span", { class: "loop-chip loop-stop" }, "Stopped by code")
    : h("span", { class: "loop-chip" }, running ? `${ROLES.bid_manager} working…` : "Next round"));
  return chips;
}

// --- One Bid Manager round and the re-vote that followed it ---

function changeRow(change) {
  if (change.outcome !== "applied") {
    return h("div", { class: "change refused" },
      h("span", { class: "num change-id" }, objectionId(change.objection_id)),
      h("span", { class: "muted" }, `Refused by code: ${REFUSAL_WORDS[change.outcome]}${change.claim_id ? ` (${statementId(change.claim_id)})` : ""}.`));
  }
  const old = change.old_text ? h("del", { class: "old-text" }, change.old_text) : null;
  const next = change.new_text ? h("span", {}, change.new_text) : h("span", { class: "muted" }, "Removed.");
  return h("div", { class: "change" },
    h("span", { class: "num change-id" }, objectionId(change.objection_id)),
    h("div", { class: "change-body" },
      h("span", { class: "change-action" }, ACTION_WORDS[change.action]),
      old, next));
}

function seatNote(seat, tracker) {
  if (seat.status === "not_reviewed") return `${WORDS.notAnswered} Retry the reviewer.`;
  const open = tracker.filter((t) => t.seat === seat.seat_id && t.status === "open").map((t) => objectionId(t.id));
  if (seat.condition) return `${seat.condition}${open.length ? ` (${open.join(", ")})` : ""}`;
  return open.length ? `Still open: ${open.join(", ")}` : "Nothing open.";
}

// Before → after with an arrow and colour: up, down or the same. A missing score shows "—".
export function scoreMove(before, after) {
  const known = (v) => v !== null && v !== undefined;
  const text = `${known(before) ? scoreText(before) : "—"} → ${known(after) ? scoreText(after) : "—"}`;
  if (!known(before) || !known(after)) return h("span", { class: "move" }, text);
  const diff = Math.round((after - before) * 100) / 100;
  const [arrow, cls, word] = diff > 0 ? ["▲", "move-up", "up"] : diff < 0 ? ["▼", "move-down", "down"] : ["=", "move-same", "the same"];
  return h("span", { class: `move ${cls}`, title: `Score ${word}` }, text, " ", h("span", { "aria-hidden": "true" }, arrow));
}

function voteRow(seat, before, tracker) {
  const score = seat.kind === "gate"
    ? h("span", { class: "gate-tag" }, WORDS.signOffShort)
    : scoreMove(before ? before.score : null, seat.score);
  return h("div", { class: "vote-row" },
    h("strong", {}, seat.title),
    h("span", { class: "num muted" }, score),
    decisionPill(seat),
    h("span", { class: "vote-note" }, seatNote(seat, tracker)));
}

// One line for a collapsed round: changes applied, and how many scoring reviewers moved.
export function roundSummary(bidRound, before, after) {
  const applied = bidRound.changes.filter((c) => c.outcome === "applied").length;
  let up = 0;
  let down = 0;
  for (const seat of after.seats.filter((s) => s.kind === "scoring")) {
    const prior = before.seats.find((s) => s.seat_id === seat.seat_id);
    if (!prior || prior.score === null || prior.score === undefined || seat.score === null || seat.score === undefined) continue;
    if (seat.score > prior.score) up += 1;
    if (seat.score < prior.score) down += 1;
  }
  return `Round ${bidRound.no}: ${plural(applied, "change", "changes")}, ${reviewerCount(up)} up, ${down} down`;
}

export function bidRoundCard(bidRound, step, before, after, tracker, stopped, expanded = true) {
  const answered = bidRound.answered.length ? `answered ${bidRound.answered.map(objectionId).join(", ")}` : "answered nothing";
  const previous = Object.fromEntries(before.seats.map((s) => [s.seat_id, s]));
  const open = tracker.filter((t) => t.status === "open");
  const objections = open.filter((t) => t.kind === "O").map((t) => objectionId(t.id));
  const conditions = open.filter((t) => t.kind === "C").length;
  const handBack = stopped || !open.length
    ? null
    : handLine(`Hands to ${ROLES.bid_manager}: ${objections.length ? `the open objections (${objections.join(", ")})` : "no open objections"}${conditions ? ` and ${plural(conditions, "condition", "conditions")}` : ""}.`);
  // Two cards per round (design v12): what the Revision Editor changed, then the board's vote on
  // it, in one block that collapses to a one-line summary.
  return h("details", { class: "round-pair", open: expanded },
    h("summary", { class: "round-summary" }, roundSummary(bidRound, before, after)),
    h("article", { class: "card round-card" },
      h("div", { class: "agent-head" },
        h("strong", {}, `${ROLES.bid_manager} · round ${bidRound.no}`),
        step ? modelChip(step) : null,
        h("span", { class: "num agent-time" }, `${step ? seconds(step.duration_ms) : ""} · ${answered}`)),
      h("div", { class: "change-list" }, ...bidRound.changes.map(changeRow),
        ...(bidRound.not_answered || []).map(notAnsweredRow))),
    h("article", { class: "card round-card" },
      h("div", { class: "agent-head" },
        h("strong", {}, `Board vote · round ${after.no}`),
        h("span", { class: "muted small" }, `The whole board read draft ${bidRound.draft_no}.`)),
      h("div", { class: "vote-list" }, ...after.seats.map((s) => voteRow(s, previous[s.seat_id], tracker))),
      handBack));
}

// --- Side column: scores by round, gates by round, why the loop stopped, the tracker ---

export function scoresByRound(rounds) {
  const scoring = rounds[0].seats.filter((s) => s.kind === "scoring");
  const blocks = scoring.map((seat) => {
    const rows = rounds.map((round) => {
      const result = round.seats.find((s) => s.seat_id === seat.seat_id);
      const score = result && result.score !== null && result.score !== undefined ? result.score : null;
      const label = score === null ? "not reviewed" : scoreText(score);
      return h("div", { class: "round-bar" },
        h("span", { class: "num" }, `R${round.no}`),
        h("div", { class: "bar small-bar", role: "img", "aria-label": `Round ${round.no}: ${label}, needs ${seat.needed.toFixed(1)}` },
          h("span", { class: "bar-fill fill-round", style: `width: ${(score || 0) * 10}%` }),
          h("span", { class: "bar-tick", style: `left: ${seat.needed * 10}%` })),
        h("span", { class: "num" }, label));
    });
    return h("div", { class: "round-seat" },
      h("div", {}, h("strong", {}, seat.title), h("span", { class: "num muted" }, ` needs ${seat.needed.toFixed(1)}`)),
      ...rows);
  });
  return [h("h2", {}, "Scores by round"), ...blocks,
    h("p", { class: "muted small" }, "The black tick is the score each executive needs."),
    h("p", { class: "muted small" }, SCORES_MOVE)];
}

export function gatesByRound(rounds) {
  const gates = rounds[0].seats.filter((s) => s.kind === "gate");
  if (!gates.length) return [];
  const rows = gates.map((gate) => {
    const chips = [];
    rounds.forEach((round, i) => {
      const result = round.seats.find((s) => s.seat_id === gate.seat_id);
      if (i) chips.push(h("span", { class: "loop-arrow", "aria-hidden": "true" }, "→"));
      const cls = result && result.outcome ? GATE_CLASSES[result.outcome] : "pill-none";
      chips.push(h("span", { class: `pill ${cls}`, title: result ? decisionText(result) : "" }, `R${round.no}: ${result ? decisionText(result) : "—"}`));
    });
    return h("div", { class: "gate-round" }, h("span", {}, gate.title), h("div", { class: "chips" }, ...chips));
  });
  return [h("h2", { class: "sub-h" }, `${WORDS.signOffTitle} by round`), ...rows];
}

export function whyStopped(stop) {
  if (!stop || !stop.stopped) return [h("h2", {}, "The loop is still running")];
  return [
    h("h2", {}, "Why the loop stopped"),
    h("div", { class: "msg m-info" }, h("ul", { class: "why-list" }, ...stop.lines.map((line) => h("li", {}, codeText(line))))),
    h("p", { class: "muted small" }, "Fixed rules decide when the loop stops, never an agent: every reviewer can approve, the scores stop improving, the round limit is reached, or the cost guard trips."),
  ];
}

function trackerStatus(item) {
  if (item.status === "fixed") {
    const fixedIn = item.history.find((entry) => entry.state === "resolved");
    const bid = fixedIn ? fixedIn.round - 1 : null;
    return h("span", { class: "pill pill-good" }, bid ? STATUS.resolvedIn(bid) : STATUS.resolved);
  }
  if (item.kind === "C") return h("span", { class: "pill pill-cond" }, STATUS.askClient);
  if (item.decision) return h("span", { class: "pill pill-bad" }, STATUS.decision);
  if (item.answered_in.length) return h("span", { class: "pill pill-cond" }, STATUS.awaiting);
  return h("span", { class: "pill pill-bad" }, STATUS.open);
}

export function trackerList(tracker) {
  const ordered = [...tracker].sort((a, b) => (a.kind !== b.kind ? (a.kind === "O" ? -1 : 1) : Number(a.id.slice(1)) - Number(b.id.slice(1))));
  return [
    h("h2", {}, "Objection tracker"),
    h("div", { class: "tracker-list" }, ...ordered.map((t) => h("div", { class: "tracker-row" },
      h("span", { class: "num tracker-id" }, objectionId(t.id)),
      h("span", { class: "tracker-text" }, t.text),
      h("span", { class: "tracker-status" }, trackerStatus(t))))),
    h("p", { class: "muted small" }, `An objection counts as resolved only after the reviewer who raised it has read the new text and agreed. "${STATUS.awaiting}" means the ${ROLES.bid_manager} changed the proposal; the reviewer has not agreed yet.`),
  ];
}

// The latest change code applied for an objection, across every Bid Manager round.
function lastChange(revisions, id) {
  const applied = revisions.flatMap((r) => r.changes)
    .filter((c) => c.objection_id === id && c.outcome === "applied");
  return applied.length ? applied[applied.length - 1] : null;
}

const CHANGE_CHIPS = { add: "chip-good", replace: "chip-good", assume: "chip-cond", remove: "chip-none" };

export function objectionsTable(tracker, seats, revisions) {
  const titles = Object.fromEntries(seats.map((s) => [s.seat_id, s.title]));
  const ordered = [...tracker].sort((a, b) => (a.kind !== b.kind ? (a.kind === "O" ? -1 : 1) : Number(a.id.slice(1)) - Number(b.id.slice(1))));
  const rows = ordered.map((t) => {
    const change = lastChange(revisions, t.id);
    const text = change ? change.new_text || "Removed." : "";
    const what = change
      ? h("div", { class: "what-changed" },
          h("span", { class: `chk-chip ${CHANGE_CHIPS[change.action]}` }, ACTION_WORDS[change.action]),
          h("span", { class: "one-line", title: text }, text))
      : h("span", { class: "muted" }, `Not changed by the ${ROLES.bid_manager}`);
    return h("tr", {},
      h("td", { class: "num" }, h("strong", {}, objectionId(t.id))),
      h("td", {}, titles[t.seat] || t.seat),
      h("td", {}, t.text, t.claim_ids.length ? h("span", { class: "num claim-id" }, ` ${t.claim_ids.map(statementId).join(", ")}`) : null),
      h("td", {}, what),
      h("td", {}, trackerStatus(t)));
  });
  return [
    h("div", { class: "log-head" },
      h("h2", {}, "Objections and what changed"),
      h("span", { class: "muted small" }, "The latest change code applied for each objection; full text in the tooltip.")),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ...["ID", "Raised by", "Challenge", "What changed", "Status"].map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", {}, ...rows))),
  ];
}

export function loopStats(steps) {
  const ms = steps.reduce((n, s) => n + s.duration_ms, 0);
  const cost = steps.reduce((n, s) => n + s.cost_usd, 0);
  return [
    h("span", {}, plural(steps.length, "agent call", "agent calls")),
    h("span", { class: "num", title: "Agent time added up. Cost is estimated from token counts at list prices; it is not a bill." },
      `${Math.round(ms / 1000)} s · $${cost.toFixed(2)} est.`),
  ];
}

// --- The final report ---

// The ring shows the final average of the scoring seats, read from the report's own key number
// ("6.2 → 7.2"), never computed here. Without that number there is no ring.
const AVERAGE_LABEL = "Average score, scoring seats";
export function finalAverage(numbers) {
  const average = (numbers || []).find((n) => n.label === AVERAGE_LABEL);
  if (!average) return null;
  const last = average.value.split("→").pop().trim();
  return /^\d+(\.\d+)?$/.test(last) ? last : null;
}

function scoreRing(numbers) {
  const value = finalAverage(numbers);
  if (value === null) return null;
  const percent = Math.max(0, Math.min(100, Math.round(Number(value) * 10)));
  return h("div", { class: "score-ring", style: `--p: ${percent}`, role: "img", "aria-label": `Final average score ${value} of 10` },
    h("span", { class: "ring-in" }, h("span", { class: "num" }, value), h("small", {}, "of 10")));
}

export function verdictBanner(report, onPrint, onDownload) {
  return h("section", { class: `verdict ${VERDICT_CLASSES[report.verdict_code] || "verdict-warn"}`, "aria-labelledby": "verdict-h" },
    scoreRing(report.numbers),
    h("div", { class: "verdict-text" },
      h("span", { class: "num eyebrow-light" }, "VERDICT"),
      h("h1", { id: "verdict-h" }, report.verdict),
      h("strong", { class: "tnum verdict-headline" }, report.headline),
      h("p", {}, codeText(report.summary))),
    h("div", { class: "verdict-actions no-print" },
      button("Print or save as PDF", "btn btn-light small-btn", onPrint),
      button("Download this run", "btn btn-ghost small-btn", onDownload)));
}

export function keyNumbers(numbers) {
  return numbers.map((n) => {
    const day = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (.+)$/.exec(n.value);
    const value = day
      ? [h("strong", { class: "tnum key-value nowrap" }, day[2]), h("span", { class: "small key-day" }, WEEKDAYS[day[1]])]
      : [h("strong", { class: "tnum key-value" }, n.value)];
    return h("div", { class: "card key-number" },
      h("span", { class: "muted small" }, codeText(n.label)),
      ...value,
      n.note ? h("span", { class: "muted small" }, codeText(n.note)) : null);
  });
}

// Each scoring reviewer's draft 1 score and final score, with the move.
export function scoreMoves(rounds) {
  const first = rounds[0];
  const last = rounds[rounds.length - 1];
  const scoring = first.seats.filter((s) => s.kind === "scoring");
  if (!scoring.length) return [];
  const rows = scoring.map((seat) => {
    const final = last.seats.find((s) => s.seat_id === seat.seat_id);
    return h("li", {}, h("span", {}, seat.title), scoreMove(seat.score, final ? final.score : null));
  });
  return [
    h("h2", {}, "Scores by reviewer, draft 1 → final"),
    h("ul", { class: "move-list" }, ...rows),
    h("p", { class: "muted small" }, SCORES_MOVE),
  ];
}

// The objection in words, cut to fit with the full text in the title, then its shown id.
function objectionWords(id, tracker) {
  const item = tracker.find((t) => t.id === id);
  if (!item) return h("span", { class: "change-obj" }, h("span", { class: "num change-id" }, objectionId(id)));
  return h("span", { class: "change-obj", title: item.text },
    trimmed(item.text, CHANGE_TEXT_MAX), " ", h("span", { class: "num change-id" }, objectionId(id)));
}

export function changesSince(changes, notAnswered = [], tracker = []) {
  const rows = changes.length
    ? changes.map((c) => h("li", { class: "change-line" },
        objectionWords(c.objection_id, tracker),
        h("span", { class: "change-action" }, `${c.action}, round ${c.round}`),
        h("span", {}, c.text)))
    : [h("li", { class: "muted" }, `No change was made: the loop stopped before a ${ROLES.bid_manager} round.`)];
  return [
    h("div", { class: "card-title-row" }, h("h2", {}, "What changed since draft 1"),
      h("span", { class: "muted small" }, "Each change answers one objection")),
    h("ol", { class: "changes-list" }, ...rows),
    notAnswered.length ? h("strong", { class: "small" }, `Not answered by the ${ROLES.bid_manager}`) : null,
    notAnswered.length
      ? h("ol", { class: "changes-list" }, ...notAnswered.map((c) => h("li", { class: "change-line" },
          objectionWords(c.objection_id, tracker),
          h("span", { class: "change-action" }, `round ${c.round}`),
          h("span", {}, c.text))))
      : null,
  ].filter(Boolean);
}

export function finalProposal(claims, draftNo, client) {
  return proposal(claims, `Proposal for ${client} · ${W.finalDraft} (draft ${draftNo})`, "final-h");
}

export function decisionMemo(memo) {
  const rows = memo.map((m) => h("tr", {},
    h("td", {}, h("strong", {}, m.title)),
    h("td", {}, decisionPill(m)),
    h("td", { class: "num" }, m.score === null || m.score === undefined ? (m.vote ? "—" : WORDS.signOffShort) : `${scoreText(m.score)} / ${m.needed.toFixed(1)}`),
    h("td", {}, m.reason)));
  return [
    h("div", { class: "log-head" }, h("h2", { id: "memo-h" }, "Board decision memo")),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ...["Reviewer", "Result", "Score", "Reason"].map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", {}, ...rows))),
  ];
}

// "What to do next", right under the verdict: the two lists the run already has, shown only
// here. An empty list is hidden; the whole box is hidden when both are empty.
export function whatNext(confirm, decisions = []) {
  const lists = [
    confirm.length ? h("div", {}, h("h3", {}, W.confirmWithClient), h("ol", { class: "confirm-list" }, ...confirm.map((c) => h("li", {}, c)))) : null,
    decisions.length ? h("div", {}, h("h3", {}, W.decisionsForYou), h("ol", { class: "confirm-list" }, ...decisions.map((d) => h("li", {}, d)))) : null,
  ].filter(Boolean);
  if (!lists.length) return [];
  return [h("h2", { class: "close-title" }, W.whatToDoNext), h("div", { class: "next-cols" }, ...lists)];
}

export function meetingPrep(confirm) {
  return [
    h("h2", {}, "Meeting prep"),
    h("p", { class: "muted small" }, "The Presales Lead's questions and next steps arrive in a later build."),
    confirm.length ? null : h("p", { class: "muted small" }, "Nothing is waiting for the client."),
  ].filter(Boolean);
}

export function prototypeCard() {
  return [
    h("div", {}, h("h2", {}, "See what Phase 1 could look like"),
      h("p", { class: "muted small" }, "The UX Designer's concept screen arrives in a later build.")),
    button("Show prototype preview", "btn btn-primary small-btn no-print", null, true),
  ];
}
