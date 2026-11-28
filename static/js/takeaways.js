// One takeaway sentence per stage, built by code from data already in the run (never by an AI
// call) and shown as plain text. A clause whose data is missing is left out, never left blank.

import { STATUS, WORDS, plural, reviewerCount, statementCount, trimmed } from "./labels.js";
import { longDate, money, scoreText, teamText } from "./render.js";

const DECISION_TEXT_MAX = 90;
const NEXT_TEXT_MAX = 140;

function sentence(parts) {
  return parts.filter(Boolean).join("");
}

export function teamTakeaway(data) {
  const claims = data.claims || [];
  const cost = data.estimate ? money(data.estimate.total, data.estimate.currency) : null;
  const team = data.efforts && data.efforts.length ? teamText(data.efforts) : null;
  const golive = data.schedule ? longDate(data.schedule.go_live) : null;
  const money_part = cost && team ? `${cost} for ${team}` : cost || (team ? `a team of ${team}` : null);
  const extras = [money_part, golive ? `go-live ${golive}` : null].filter(Boolean);
  return sentence([`Draft 1 is ready: ${statementCount(claims.length)} in 9 sections`, extras.length ? `, ${extras.join(", ")}` : "", "."]);
}

// The board's biggest gap: the scoring reviewer furthest below its needed score, else the first
// blocked sign-off check.
export function biggestGap(round) {
  const below = round.seats
    .filter((s) => s.kind === "scoring" && s.score !== null && s.score !== undefined && s.score < s.needed)
    .sort((a, b) => (b.needed - b.score) - (a.needed - a.score));
  if (below.length) {
    const s = below[0];
    return `the ${s.title} at ${scoreText(s.score)} of 10, needs ${s.needed.toFixed(1)}`;
  }
  const blocked = round.seats.find((s) => s.kind === "gate" && s.outcome === "blocked");
  return blocked ? `the ${blocked.title} blocks it` : null;
}

export function boardTakeaway(round) {
  const { able, total } = round.progress;
  const cleared = able === 0 ? "did not clear" : able === total ? "cleared" : "partly cleared";
  const gap = able === total ? null : biggestGap(round);
  return sentence([
    `The board ${cleared} this draft: ${able} of ${reviewerCount(total)} can approve.`,
    gap ? ` Biggest gap: ${gap}.` : "",
  ]);
}

export function loopTakeaway(revisions, tracker, seats) {
  const objections = tracker.filter((t) => t.kind === "O");
  const resolved = objections.filter((t) => t.status === "fixed").length;
  const rounds = revisions.length;
  const lead = rounds
    ? `After ${plural(rounds, "round", "rounds")}, ${resolved} of ${plural(objections.length, "objection", "objections")} ${resolved === 1 ? "is" : "are"} resolved.`
    : `No revision round ran: ${resolved} of ${plural(objections.length, "objection", "objections")} resolved.`;
  const decision = tracker.find((t) => t.kind === "O" && t.status === "open" && t.decision);
  if (!decision) return lead;
  const seat = seats.find((s) => s.seat_id === decision.seat);
  const who = seat ? `The ${seat.title}` : "A reviewer";
  return `${lead} ${who} still raises a point that is ${STATUS.decision.replace(/^Needs /, "").toLowerCase()}: ${trimmed(decision.text, DECISION_TEXT_MAX)}`;
}

export function reportTakeaway(report) {
  const confirm = report.confirm_with_client || [];
  const decisions = report.decisions || [];
  const next = confirm.length
    ? `First, ${WORDS.confirmWithClient.toLowerCase()}: ${trimmed(confirm[0], NEXT_TEXT_MAX)}`
    : decisions.length
      ? `First, decide: ${trimmed(decisions[0], NEXT_TEXT_MAX)}`
      : "Nothing is waiting for the client.";
  return `${report.verdict}. ${next}`;
}
