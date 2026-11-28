// The labels file: display names for internal codes and ids. Internal codes never change.

import assert from "node:assert/strict";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import "./fake-dom.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const labels = await import(pathToFileURL(path.join(here, "..", "..", "static", "js", "labels.js")).href);

// Ids as shown: #n for objections, Qn for client-only items, Sn for statements.
assert.equal(labels.objectionId("O12"), "#12");
assert.equal(labels.objectionId("C3"), "Q3");
assert.equal(labels.objectionId("X9"), "X9");
assert.equal(labels.statementId("C7"), "S7");

// Role and term renames in code-written text only.
assert.equal(labels.codeText("Hands to Bid Manager: the open objections, each with its id."), "Hands to Revision Editor: the open objections, each with its id.");
assert.equal(labels.codeText("Wrote draft 1 as 15 short claims in 9 sections."), "Wrote draft 1 as 15 short statements in 9 sections.");
assert.equal(labels.codeText("Code decided: Pass, with conditions."), "Code decided: Signed off, with conditions.");
assert.equal(labels.codeText("3 of 5 board seats can proceed."), "3 of 5 reviewers can approve this draft.");
labels.setClientIds([{ id: "C2", kind: "C" }, { id: "O4", kind: "O" }]);
assert.equal(labels.codeText("Not answered by the Bid Manager: O4, C2."), "Not answered by the Revision Editor: #4, Q2.");
// A statement id that looks like a client id is left alone unless the tracker has that client item.
assert.equal(labels.codeText("Code re-tagged C7 TO CONFIRM."), "Code re-tagged C7 TO CONFIRM.");
labels.setClientIds([]);
assert.equal(labels.codeText("answered C2"), "answered C2");
assert.equal(labels.codeText("+4 conditions to confirm"), "+4 items for the client to confirm");
assert.equal(labels.codeText("and set 5 context flags."), "and set 5 key facts.");
assert.equal(labels.codeText("the case file. The 5 flags choose the board."), "the case file. The 5 key facts choose the board.");
assert.equal(labels.codeText(undefined), "");

assert.equal(labels.keyNote("+4 conditions to confirm"), "4 items for the client to confirm");
assert.equal(labels.keyLabel("Objections fixed"), "Objections resolved");

// Gate outcomes and statuses.
assert.equal(labels.OUTCOMES.pass_with_conditions, "Signed off, with conditions");
assert.equal(labels.STATUS.resolvedIn(2), "Resolved in round 2");
assert.equal(labels.MODES.Full, "Live run");
assert.equal(labels.reviewerCount(1), "1 reviewer");
assert.equal(labels.statementCount(17), "17 statements");

// One name per reviewer: the seat title once the plan is known, the role label otherwise.
{
  const plan = { seats: [{ id: "vp_director", title: "VP, Customer Support" }] };
  assert.equal(labels.stepName({ agent: "vp_director", label: "VP or Director" }, plan), "VP, Customer Support");
  assert.equal(labels.stepName({ agent: "vp_director", label: "VP or Director" }, null), "VP or Director");
  assert.equal(labels.stepName({ agent: "bid_manager", label: "Bid Manager" }, plan), "Revision Editor");
  assert.equal(labels.stepName({ agent: "business_analyst", label: "Business Analyst" }, plan), "Business Analyst");
}

process.stdout.write("labels: all checks passed\n");
