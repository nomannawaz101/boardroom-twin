// Stages 4 and 5: the revision loop and the final report. Built from server responses; all AI
// text goes in as text nodes (guard G12). Every number shown was computed by code.

import {
  button, decisionPill, h, handLine, modelChip, proposal, scoreText, seconds,
} from "./render.js";

const GATE_CLASSES = { pass: "pill-good", pass_with_conditions: "pill-cond", blocked: "pill-bad" };
const VERDICT_CLASSES = {
  approved: "verdict-good", approved_with_conditions: "verdict-good",
  review_incomplete: "verdict-warn", not_ready: "verdict-bad",
};
const ACTION_WORDS = { replace: "Changed", remove: "Removed", add: "Added", assume: "Assumption" };
const REFUSAL_WORDS = {
  locked: "a calculated claim is locked",
  unknown_claim: "no such claim",
  unknown_objection: "no open objection with that id",
  empty: "no text",
  client_only: "only the client can settle this, so it can only be an assumption",
  protected: "commercial facts, dates and brief claims can only change through an assumption",
  duplicate: "the same assumption is already in the proposal",
};

function notAnsweredRow(id) {
  return h("div", { class: "change refused" },
    h("span", { class: "num change-id" }, id),
    h("span", { class: "muted" }, "Not answered by the Bid Manager."));
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

// --- Loop chips: "Board round 1: 2 of 5 can proceed" → … → "Stopped by code" ---

export function loopChips(rounds, stop, running) {
  const chips = [];
  rounds.forEach((round, i) => {
    const text = i === 0
      ? `Board round 1: ${round.progress.able} of ${round.progress.total} can proceed`
      : `Bid round ${i} → Board round ${round.no}: ${round.progress.able} of ${round.progress.total}`;
    if (i) chips.push(h("span", { class: "loop-arrow", "aria-hidden": "true" }, "→"));
    chips.push(h("span", { class: "loop-chip" }, text));
  });
  chips.push(h("span", { class: "loop-arrow", "aria-hidden": "true" }, "→"));
  chips.push(stop && stop.stopped
    ? h("span", { class: "loop-chip loop-stop" }, "Stopped by code")
    : h("span", { class: "loop-chip" }, running ? "Bid Manager working…" : "Next round"));
  return chips;
}

// --- One Bid Manager round and the re-vote that followed it ---

function changeRow(change) {
  if (change.outcome !== "applied") {
    return h("div", { class: "change refused" },
      h("span", { class: "num change-id" }, change.objection_id),
      h("span", { class: "muted" }, `Refused by code: ${REFUSAL_WORDS[change.outcome]}${change.claim_id ? ` (${change.claim_id})` : ""}.`));
  }
  const old = change.old_text ? h("del", { class: "old-text" }, change.old_text) : null;
  const next = change.new_text ? h("span", {}, change.new_text) : h("span", { class: "muted" }, "Removed.");
  return h("div", { class: "change" },
    h("span", { class: "num change-id" }, change.objection_id),
    h("div", { class: "change-body" },
      h("span", { class: "change-action" }, ACTION_WORDS[change.action]),
      old, next));
}

function seatNote(seat, tracker) {
  if (seat.status === "not_reviewed") return "Did not answer; retry the seat.";
  const open = tracker.filter((t) => t.seat === seat.seat_id && t.status === "open").map((t) => t.id);
  if (seat.condition) return `${seat.condition}${open.length ? ` (${open.join(", ")})` : ""}`;
  return open.length ? `Still open: ${open.join(", ")}` : "Nothing open.";
}

function voteRow(seat, before, tracker) {
  const score = seat.kind === "gate"
    ? "gate"
    : `${before && before.score !== null && before.score !== undefined ? scoreText(before.score) : "—"} → ${seat.score === null || seat.score === undefined ? "—" : scoreText(seat.score)}`;
  return h("div", { class: "vote-row" },
    h("strong", {}, seat.title),
    h("span", { class: "num muted" }, score),
    decisionPill(seat),
    h("span", { class: "vote-note" }, seatNote(seat, tracker)));
}

export function bidRoundCard(bidRound, step, before, after, tracker, stopped) {
  const answered = bidRound.answered.length ? `answered ${bidRound.answered.join(", ")}` : "answered nothing";
  const previous = Object.fromEntries(before.seats.map((s) => [s.seat_id, s]));
  const open = tracker.filter((t) => t.status === "open");
  const objections = open.filter((t) => t.kind === "O").map((t) => t.id);
  const conditions = open.filter((t) => t.kind === "C").length;
  const handBack = stopped || !open.length
    ? null
    : handLine(`Hands to Bid Manager: ${objections.length ? `the open objections (${objections.join(", ")})` : "no open objections"}${conditions ? ` and ${plural(conditions, "condition", "conditions")}` : ""}.`);
  return h("article", { class: "card round-card" },
    h("div", { class: "agent-head" },
      h("strong", {}, `Bid Manager · round ${bidRound.no}`),
      step ? modelChip(step) : null,
      h("span", { class: "num agent-time" }, `${step ? seconds(step.duration_ms) : ""} · ${answered}`)),
    h("div", { class: "change-list" }, ...bidRound.changes.map(changeRow),
      ...(bidRound.not_answered || []).map(notAnsweredRow)),
    h("div", { class: "vote-list" }, ...after.seats.map((s) => voteRow(s, previous[s.seat_id], tracker))),
    handBack);
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
    h("p", { class: "muted small" }, "The black tick is the score each executive needs.")];
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
      chips.push(h("span", { class: `pill ${cls}`, title: result ? result.decision : "" }, `R${round.no}: ${result ? result.decision : "—"}`));
    });
    return h("div", { class: "gate-round" }, h("span", {}, gate.title), h("div", { class: "chips" }, ...chips));
  });
  return [h("h2", { class: "sub-h" }, "Gates by round"), ...rows];
}

export function whyStopped(stop) {
  if (!stop || !stop.stopped) return [h("h2", {}, "The loop is still running")];
  return [
    h("h2", {}, "Why the loop stopped"),
    h("ul", { class: "why-list" }, ...stop.lines.map((line) => h("li", {}, line))),
    h("p", { class: "muted small" }, "Code decides when the loop stops, never an agent: every seat can proceed, the scores stop improving, the round limit is reached, or the cost guard trips."),
  ];
}

function trackerStatus(item) {
  if (item.status === "fixed") {
    const fixedIn = item.history.find((entry) => entry.state === "resolved");
    const bid = fixedIn ? fixedIn.round - 1 : null;
    return h("span", { class: "pill pill-good" }, bid ? `Fixed R${bid}` : "Fixed");
  }
  if (item.kind === "C") return h("span", { class: "pill pill-cond" }, "Confirm");
  if (item.answered_in.length) return h("span", { class: "pill pill-cond" }, "Answered");
  return h("span", { class: "pill pill-bad" }, "Open");
}

export function trackerList(tracker) {
  const ordered = [...tracker].sort((a, b) => (a.kind !== b.kind ? (a.kind === "O" ? -1 : 1) : Number(a.id.slice(1)) - Number(b.id.slice(1))));
  return [
    h("h2", {}, "Objection tracker"),
    h("div", { class: "tracker-list" }, ...ordered.map((t) => h("div", { class: "tracker-row" },
      h("span", { class: "num" }, t.id), h("span", {}, t.text), trackerStatus(t)))),
    h("p", { class: "muted small" }, "An objection counts as fixed only after the seat that raised it has read the new text and agreed. \"Answered\" means the Bid Manager changed the proposal; the seat has not agreed yet."),
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

export function verdictBanner(report, onPrint, onDownload) {
  return h("section", { class: `verdict ${VERDICT_CLASSES[report.verdict_code] || "verdict-warn"}`, "aria-labelledby": "verdict-h" },
    h("div", { class: "verdict-text" },
      h("span", { class: "num eyebrow-light" }, "VERDICT"),
      h("h1", { id: "verdict-h" }, report.verdict),
      h("strong", { class: "num verdict-headline" }, report.headline),
      h("p", {}, report.summary)),
    h("div", { class: "verdict-actions no-print" },
      button("Print or save as PDF", "btn btn-light small-btn", onPrint),
      button("Download this run", "btn btn-ghost small-btn", onDownload)));
}

export function keyNumbers(numbers) {
  return numbers.map((n) => h("div", { class: "card key-number" },
    h("span", { class: "muted small" }, n.label),
    h("strong", { class: "num key-value" }, n.value),
    n.note ? h("span", { class: "muted small" }, n.note) : null));
}

export function changesSince(changes, notAnswered = []) {
  const rows = changes.length
    ? changes.map((c) => h("li", { class: "change-line" },
        h("span", { class: "num change-id" }, c.objection_id),
        h("span", { class: "change-action" }, `${c.action}, round ${c.round}`),
        h("span", {}, c.text)))
    : [h("li", { class: "muted" }, "No change was made: the loop stopped before a Bid Manager round.")];
  return [
    h("div", { class: "card-title-row" }, h("h2", {}, "What changed since draft 1"),
      h("span", { class: "muted small" }, "Each change answers one objection")),
    h("ol", { class: "changes-list" }, ...rows),
    notAnswered.length ? h("strong", { class: "small" }, "Not answered by the Bid Manager") : null,
    notAnswered.length
      ? h("ol", { class: "changes-list" }, ...notAnswered.map((c) => h("li", { class: "change-line" },
          h("span", { class: "num change-id" }, c.objection_id),
          h("span", { class: "change-action" }, `round ${c.round}`),
          h("span", {}, c.text))))
      : null,
  ].filter(Boolean);
}

export function finalProposal(claims, draftNo, client) {
  return proposal(claims, `Proposal for ${client} · final version (draft ${draftNo})`, "final-h");
}

export function decisionMemo(memo) {
  const rows = memo.map((m) => h("tr", {},
    h("td", {}, h("strong", {}, m.title)),
    h("td", {}, decisionPill(m)),
    h("td", { class: "num" }, m.score === null || m.score === undefined ? (m.vote ? "—" : "gate") : `${scoreText(m.score)} / ${m.needed.toFixed(1)}`),
    h("td", {}, m.reason)));
  return [
    h("div", { class: "log-head" }, h("h2", { id: "memo-h" }, "Board decision memo")),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ...["Seat", "Result", "Score", "Reason"].map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", {}, ...rows))),
  ];
}

export function meetingPrep(confirm) {
  return [
    h("h2", {}, "Meeting prep"),
    h("p", { class: "muted small" }, "The Presales Lead's questions and next steps arrive in a later build."),
    h("strong", { class: "small" }, "Confirm with the client"),
    confirm.length
      ? h("ol", { class: "confirm-list" }, ...confirm.map((c) => h("li", {}, c)))
      : h("p", { class: "muted small" }, "Nothing is waiting for the client."),
  ];
}

export function prototypeCard() {
  return [
    h("div", {}, h("h2", {}, "See what Phase 1 could look like"),
      h("p", { class: "muted small" }, "The UX Designer's concept screen arrives in a later build.")),
    button("Show prototype preview", "btn btn-primary small-btn no-print", null, true),
  ];
}
