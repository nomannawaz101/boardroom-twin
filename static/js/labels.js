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

// Static page texts, filled into every [data-text] element when the page starts.
export const PAGE_TEXT = {
  "step-1": `Business Analyst, Solution Architect, Delivery Manager, Risk & Compliance Analyst and ${ROLES.proposal_manager} hand work to each other`,
  "step-2": "3 to 5 reviewers chosen from your brief. CFO, VP or Director, Enterprise Architect, Procurement and Security vote at the same time",
  "step-3-title": `${ROLES.bid_manager} revises`,
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

// Code-written server text (step labels, summaries, handoff lines, stop lines, report notes)
// in the words the user sees. Model-written text never passes through here.
const CODE_TEXT = [
  ...ROLE_WORDS.map(([from, to]) => [new RegExp(`\\b${from}\\b`, "g"), to]),
  [/\bPass, with conditions\b/g, OUTCOMES.pass_with_conditions],
  [/\bPass\b/g, OUTCOMES.pass],
  [/\bcontext flags\b/g, "key facts"],
  [/\bconditions to confirm\b/g, "items for the client to confirm"],
  [/\bcondition to confirm\b/g, "item for the client to confirm"],
  [/\bscoring seats\b/g, WORDS.scoringReviewers],
  [/\bboard seats\b/g, WORDS.reviewers],
  [/\bEvery seat on the board\b/g, "Every reviewer"],
  [/\bseats\b/g, WORDS.reviewers],
  [/\bseat\b/g, WORDS.reviewer],
  [/\bclaims\b/g, WORDS.statements],
  [/\bclaim\b/g, WORDS.statement],
  [/\bgatekeepers\b/g, WORDS.signOffReviewers],
  [/\bgates\b/g, WORDS.signOffs],
  [/\bgate\b/g, WORDS.signOff],
  [/\bO(\d+)\b/g, "#$1"],
  [/\bC(\d+)\b/g, "Q$1"],
];

export function codeText(text) {
  return CODE_TEXT.reduce((out, [pattern, to]) => out.replace(pattern, to), String(text || ""));
}
