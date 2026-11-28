// Takeaway lines: built by code from run data; a clause with no data is left out.

import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import "./fake-dom.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const take = await import(pathToFileURL(path.join(here, "..", "..", "static", "js", "takeaways.js")).href);

// Proposal team: statements, cost for the team, go-live; missing parts are left out.
{
  const data = {
    claims: new Array(15).fill({}),
    estimate: { total: 24000, currency: "USD" },
    efforts: [{ no: 1, engineers: 2, weeks: 4 }],
    schedule: { go_live: "2027-01-04" },
  };
  assert.equal(take.teamTakeaway(data), "Draft 1 is ready: 15 statements in 9 sections, $24,000 for 2 engineers, 4 weeks, go-live Mon Jan 4, 2027.");
  assert.equal(take.teamTakeaway({ claims: [{}], estimate: null, efforts: [], schedule: null }), "Draft 1 is ready: 1 statement in 9 sections.");
  assert.equal(take.teamTakeaway({ claims: [], efforts: [{ no: 1, engineers: 3, weeks: 2 }] }), "Draft 1 is ready: 0 statements in 9 sections, a team of 3 engineers, 2 weeks.");
}

// Client board: cleared, partly or not, with the biggest gap.
{
  const seat = (id, kind, fields) => ({ seat_id: id, kind, title: id.toUpperCase(), ...fields });
  const round = {
    progress: { able: 0, total: 3 },
    seats: [
      seat("cfo", "scoring", { score: 6.1, needed: 7.0 }),
      seat("ea", "scoring", { score: 5.05, needed: 8.0 }),
      seat("so", "gate", { outcome: "blocked" }),
    ],
  };
  assert.equal(take.boardTakeaway(round), "The board did not clear this draft: 0 of 3 reviewers can approve. Biggest gap: the EA at 5.05 of 10, needs 8.0.");
  const gateOnly = { progress: { able: 1, total: 2 }, seats: [seat("cfo", "scoring", { score: 8, needed: 7 }), seat("so", "gate", { outcome: "blocked" })] };
  assert.equal(take.boardTakeaway(gateOnly), "The board partly cleared this draft: 1 of 2 reviewers can approve. Biggest gap: the SO blocks it.");
  assert.equal(take.boardTakeaway({ progress: { able: 2, total: 2 }, seats: [] }), "The board cleared this draft: 2 of 2 reviewers can approve.");
}

// Revisions: rounds, resolved count, and the decision clause only when one is open.
{
  const tracker = [
    { id: "O1", kind: "O", seat: "cfo", status: "fixed" },
    { id: "O2", kind: "O", seat: "cfo", status: "open", decision: true, text: "A firm fixed price is needed before we sign." },
    { id: "C1", kind: "C", seat: "cfo", status: "open" },
  ];
  const seats = [{ seat_id: "cfo", title: "CFO" }];
  assert.equal(take.loopTakeaway([{}, {}], tracker, seats), "After 2 rounds, 1 of 2 objections is resolved. The CFO still raises a point that is your decision: A firm fixed price is needed before we sign.");
  assert.equal(take.loopTakeaway([{}], tracker.slice(0, 1), seats), "After 1 round, 1 of 1 objection is resolved.");
}

// Report: the verdict plus the first thing to do.
{
  const report = { verdict: "Not ready yet", confirm_with_client: ["API access is unconfirmed."], decisions: ["A cap."] };
  assert.equal(take.reportTakeaway(report), "Not ready yet. First, confirm with the client: API access is unconfirmed.");
  assert.equal(take.reportTakeaway({ ...report, confirm_with_client: [] }), "Not ready yet. First, decide: A cap.");
  assert.equal(take.reportTakeaway({ verdict: "Approved" }), "Approved. Nothing is waiting for the client.");
}

process.stdout.write("takeaways: all checks passed\n");
