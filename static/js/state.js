// The run state lives in the browser and goes back with each stage request (plan section 7.2).
// It never holds a key or a passcode. The server validates it on every request.

export const BRIEF_MAX_CHARS = 15000;

const SERVER_KEYS = [
  "run_id", "mode", "brief", "case_file", "flags", "board_plan", "design", "estimate",
  "schedule", "claims", "draft_no", "rounds", "tracker", "verdict", "steps",
];

export const run = {
  data: null,
  busy: false,
};

export function startRun(discovered) {
  run.data = { ...discovered, claims: [], draft_no: 0, rounds: [], tracker: [] };
}

export function addDraft(drafted) {
  run.data = {
    ...run.data,
    ...drafted,
    rounds: [],
    tracker: [],
    steps: [...run.data.steps.filter((s) => s.stage < 2), ...drafted.steps],
  };
}

export function stateForServer() {
  const state = {};
  for (const key of SERVER_KEYS) {
    if (run.data && run.data[key] !== undefined) state[key] = run.data[key];
  }
  return state;
}

export function hasDraft() {
  return Boolean(run.data && run.data.draft_no > 0);
}

export function addBoard(board) {
  run.data = {
    ...run.data,
    rounds: [board.round],
    tracker: board.tracker,
    verdict: board.verdict.code,
    verdictLabel: board.verdict,
    steps: [...run.data.steps.filter((s) => s.stage < 3), ...board.steps],
  };
}

export function addRetriedSeat(board) {
  const step = board.steps[0];
  run.data = {
    ...run.data,
    rounds: [...run.data.rounds.slice(0, -1), board.round],
    tracker: board.tracker,
    verdict: board.verdict.code,
    verdictLabel: board.verdict,
    steps: run.data.steps.map((s) => (s.agent === step.agent ? step : s)),
  };
}

export function hasBoard() {
  return Boolean(run.data && run.data.rounds && run.data.rounds.length > 0);
}
