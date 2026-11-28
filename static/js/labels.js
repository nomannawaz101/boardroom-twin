// Every name the user sees for an internal code, id or role, in one place. Internal codes, ids
// and the run JSON never change; only what is shown does. docs/wording.md lists each display
// name and what it replaces, so a rename is one edit here plus one line there.

export const ROLES = {
  bid_manager: "Revision Editor",
  proposal_manager: "Proposal Writer",
  qa_reviewer: "Fact Checker",
};

// Role names as the server writes them in code-built text (step labels, handoff lines,
// summaries), and what the user sees instead.
const ROLE_WORDS = [
  ["Bid Manager", ROLES.bid_manager],
  ["Proposal Manager", ROLES.proposal_manager],
  ["QA Reviewer", ROLES.qa_reviewer],
];

export const WORDS = {
  reviewer: "reviewer",
  reviewers: "reviewers",
  statement: "statement",
  statements: "statements",
  signOff: "sign-off check",
  signOffs: "sign-off checks",
  signOffTitle: "Sign-off checks",
  signOffShort: "sign-off",
  signOffReviewers: "sign-off reviewers",
  signOffReviewer: "sign-off reviewer",
  scoringReviewers: "scoring reviewers",
  required: "Required",
  keyFacts: "Key facts from the brief",
  fixedRules: "Fixed rules",
  ai: "AI",
  publicApi: "PUBLIC API",
  retryReviewer: "Retry this reviewer",
  retryingReviewer: "Retrying this reviewer…",
  notAnswered: "This reviewer did not answer.",
  decisionsForYou: "Decisions for you",
  confirmWithClient: "Confirm with the client",
  whatToDoNext: "What to do next",
  finalDraft: "Final draft",
  passesTo: "Passes to",
  lockedCost: "Cost fixed by code",
  aiSteps: "AI steps",
  tokens: "Tokens (AI text units)",
};

// What each seat kind does.
export const KINDS = { scoring: "Scores the proposal", gate: "Signs off or blocks it" };
export const KIND_SHORT = { scoring: "Scores", gate: "Signs off" };

// Gate outcomes; votes keep their wording.
export const OUTCOMES = {
  pass: "Signed off",
  pass_with_conditions: "Signed off, with conditions",
  blocked: "Blocked",
};

// Checklist item results from a gate answer.
export const ITEM_WORDS = { met: "Met", partly: "Partly", not_met: "Not met", missing: "Not answered" };

// Tracker statuses.
export const STATUS = {
  resolved: "Resolved",
  resolvedIn: (round) => `Resolved in round ${round}`,
  askClient: "Ask the client",
  decision: "Needs your decision",
  awaiting: "Changed, awaiting re-read",
  open: "Open",
  blocker: "Blocker",
  condition: "Condition",
};

export const MODES = { Full: "Live run", Lite: "Lite run", Sample: "Sample run" };

export const LEGEND_AI = "AI = written by a model. Fixed rules = decided by code, the same every time.";
export const LEGEND_COLOURS = "Red = rejected or blocked. Amber = conditions or to confirm. Green = met or resolved. Purple = AI. Grey = fixed rules.";
export const BOARD_SUBTITLE = "Reviewers picked by fixed rules from the key facts in the brief.";
export const CHANGE_TEXT_MAX = 90;
export const ISSUE_TEXT_MAX = 80;
export const NO_OPEN = "No open objections";

// Scores always carry their scale; weights read as percentages.
export function outOf10(score) {
  return `${score} of 10`;
}

export function needsText(needed) {
  return `needs ${needed.toFixed(1)} of 10`;
}

export function weightText(weight) {
  return `weight ${Math.round(weight * 100)}%`;
}

// Key-number labels as the server writes them, and what the user sees.
export const KEY_LABELS = {
  "Average score, scoring seats": "Average score of the scoring reviewers (out of 10)",
  "Objections fixed": "Objections resolved",
};

export function keyLabel(label) {
  return KEY_LABELS[label] || codeText(label);
}

// A key number's note in words: "+4 conditions to confirm" reads "4 items for the client to confirm".
export function keyNote(note) {
  return codeText(note).replace(/^\+(?=\d)/, "");
}
export const SCORES_MOVE = "Scores can move either way: each reviewer re-reads the whole draft from scratch, and AI ratings vary between reads.";
export const WEEKDAYS = { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday", Fri: "Friday", Sat: "Saturday", Sun: "Sunday" };

// Long text cut at a word boundary, with "…"; the full text goes in the title.
export function trimmed(text, max) {
  const value = String(text || "");
  if (value.length <= max) return value;
  const cut = value.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,.;:]+$/, "")}…`;
}


// Static page texts, filled into every [data-text] element when the page starts.
export const PAGE_TEXT = {
  "legend-ai": LEGEND_AI,
  "coming-soon": "Coming in the full build: meeting questions and a prototype preview.",
  "legend-colours": LEGEND_COLOURS,
  "hero-title": "Know what the client's board will challenge, before the meeting.",
  "hero-text": `A proposal team of AI agents writes the proposal. An AI copy of the client's evaluation board reviews it: executives who score it, and ${WORDS.signOffReviewers} who can block it. A ${ROLES.bid_manager} fixes what they object to, up to two rounds.`,
  "step-1": `Business Analyst, Solution Architect, Delivery Manager, Risk & Compliance Analyst and ${ROLES.proposal_manager} hand work to each other`,
  "step-2": "3 to 5 reviewers chosen from your brief. CFO, VP or Director, Enterprise Architect, Procurement and Security vote at the same time",
  "intro": "You are the bid team at Lumen Works, a fictional services firm. Paste a client brief or try a sample.",
  "how-1": "Brief",
  "how-1-sub": "Paste a client brief or pick a sample. Code checks it before any AI call.",
  "how-2": "The team drafts the proposal",
  "how-3": "The client's board challenges it",
  "how-4": `The ${ROLES.bid_manager} answers each objection`,
  "how-5": "You get a report you can act on",
  "how-5-sub": "Proposal, board decision memo, meeting prep, optional prototype",
  "step-3": `Up to two rounds. A ${ROLES.qa_reviewer} blocks invented statements. The board votes again`,
  "full-draft": "Read the full draft 1, statement by statement, with tags",
  "board-intro": "Fixed rules picked the board from the brief. Every reviewer reads the draft at the same time, and fixed rules turn their answers into votes.",
  "gates-title": `Round 1 · ${WORDS.signOffTitle.toLowerCase()}`,
  "gates-intro": "Sign-off reviewers answer three checklist questions. They do not give a score.",
  "gates-rule": `"Not met" on a required item → Blocked. Any "Partly", or "Not met" on another item → ${OUTCOMES.pass_with_conditions}. All "Met" → ${OUTCOMES.pass}.`,
  "loop-eyebrow": "STAGE 4 OF 5 · UP TO 2 REVISION ROUNDS",
  "loop-title": `The ${ROLES.bid_manager} is answering the objections`,
  "loop-intro": `Each round: the ${ROLES.bid_manager} changes only what was objected to, then the whole board votes again. Fixed rules decide when the loop stops.`,
};

export function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

export function reviewerCount(count) {
  return plural(count, WORDS.reviewer, WORDS.reviewers);
}

export function calculationCount(count) {
  return plural(count, "code calculation", "code calculations");
}

export function statementCount(count) {
  return plural(count, WORDS.statement, WORDS.statements);
}

// Ids as shown: objections the proposal can fix "#1", client-only items "Q1", proposal
// statements "S1". The data ids (O1, C1 and C1) never change.
export function objectionId(id) {
  const match = /^([OC])(\d+)$/.exec(String(id));
  if (!match) return String(id);
  return match[1] === "O" ? `#${match[2]}` : `Q${match[2]}`;
}

export function statementId(id) {
  const match = /^C(\d+)$/.exec(String(id));
  return match ? `S${match[1]}` : String(id);
}

export function roleName(agentId, fallback) {
  return ROLES[agentId] || fallback;
}

// One name per reviewer on every screen: once the board plan is known, a seat's step shows the
// seat title the board shows; before that, and for every other agent, the role label.
export function stepName(step, plan) {
  const seat = plan && plan.seats ? plan.seats.find((s) => s.id === step.agent) : null;
  return seat ? seat.title : roleName(step.agent, codeText(step.label));
}

// Code-written server text (step labels, summaries, handoff lines, stop lines, report notes)
// in the words the user sees. Model-written text never passes through here.
const CODE_TEXT = [
  ...ROLE_WORDS.map(([from, to]) => [new RegExp(`\\b${from}\\b`, "g"), to]),
  [/\bHands to\b/g, WORDS.passesTo],
  [/\bBoard composer\b/g, "board picker"],
  [/\ba case file\b/g, "a summary of the brief"],
  [/\bthe case file\b/g, "the summary of the brief"],
  [/\bPass, with conditions\b/g, OUTCOMES.pass_with_conditions],
  [/\bPass\b/g, OUTCOMES.pass],
  [/\bcontext flags\b/g, "key facts"],
  [/\bflags\b/g, "key facts"],
  [/\bconditions to confirm\b/g, "items for the client to confirm"],
  [/\bcondition to confirm\b/g, "item for the client to confirm"],
  [/\bscoring seats\b/g, WORDS.scoringReviewers],
  [/\bboard seats\b/g, WORDS.reviewers],
  [/\bEvery seat on the board\b/g, "Every reviewer"],
  [/\bcan proceed\b/g, "can approve"],
  [/\bseats\b/g, WORDS.reviewers],
  [/\bseat\b/g, WORDS.reviewer],
  [/\bclaims\b/g, WORDS.statements],
  [/\bclaim\b/g, WORDS.statement],
  [/\bgatekeepers\b/g, WORDS.signOffReviewers],
  [/\bgates\b/g, WORDS.signOffs],
  [/\bgate\b/g, WORDS.signOff],
  [/\b(\d+ of \d+ reviewers can approve)\./g, "$1 this draft."],
  [/\bO(\d+)\b/g, "#$1"],
];

// Client-only item ids of the current run. "C1" in code-written text becomes "Q1" only when C1
// is one of them; a statement id that looks the same (also "C1") is left as it is.
let clientIds = new Set();

export function setClientIds(tracker) {
  clientIds = new Set((tracker || []).filter((t) => t.kind === "C").map((t) => t.id));
}

export function codeText(text) {
  const words = CODE_TEXT.reduce((out, [pattern, to]) => out.replace(pattern, to), String(text || ""));
  return words.replace(/\bC(\d+)\b/g, (id, n) => (clientIds.has(id) ? `Q${n}` : id));
}
