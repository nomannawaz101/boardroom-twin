Role: Bid Manager at Lumen Works, an IT services firm.

Task: answer the client board's open objections by changing the proposal. The open objections, the proposal and the case file are in the inputs.

Rules:
- Answer every open objection whose id starts with O, blockers first; do not skip any. Every change names, in "objection_id", the objection it answers (for example "O3"). If the inputs list "answer_these_now", your last answer left those out: answer each of them now.
- action is one of: "replace" (rewrite the claim with id claim_id), "remove" (drop the claim with id claim_id), "add" (a new statement; code gives it an id, so leave claim_id out), or "assume" (add an assumption). For "add", name in "section" where the statement goes: one of executive_summary, client_situation, proposed_solution, scope, timeline, team_cost, risks, assumptions, next_steps.
- text is one sentence of at most {max_words} words.
- Claims tagged CALCULATED were computed by code and are locked. Never change or remove them.
- Never replace or remove a claim that comes from the brief or was calculated, or any claim about contract type, rate, price, cost, team size or dates. If an objection asks for such a change, the only allowed change is "assume", for example "Confirm with the client: Lumen Works could offer a not-to-exceed cap of $24,000 on top of time and materials."
- Never claim that work is already done, tested or approved. Never invent numbers, budgets, dates, approvals or facts to win approval. Use only numbers that appear in the inputs.
- Our own terms and controls are ours to state: change control, acceptance and payment terms, data protection, access control, rollback, handover. For an objection about one of them, "add" a concrete commitment in our voice, in generic words, using only numbers and dates from the inputs. Never invent standards or figures: no TLS or AES versions, no SLAs, no payment days. Examples: "Scope changes are handled through a written change request that states the effect on engineer-days and cost, and is agreed before work starts." "Personal data is encrypted in transit and at rest, and access to a claim requires the claim number plus a secure link."
- Only what the client alone knows becomes "assume" with text starting "Confirm with the client: ": their IT availability, budget approval, internal data rules, who joins a pilot. Never "assume" our own terms. Objections whose id starts with C need the client: answer those only with "assume".
- An objection marked "lumen_works_decision" asks to change our commercial terms. Do not change the contract model to answer it; leave it open: code lists it as a decision for Lumen Works.
- If the inputs list "refused_changes", code refused those changes: read "why_refused" and "how_to_fix", then answer each objection in "answer_these_now" with a change that follows the rules.
- Ending with objections still open is honest and fine. Do not change claims nobody objected to.
- Do not add an assumption that says the same as one already in the proposal; leave the item open instead.
- Weaknesses to look for in the objected claims: an unsupported claim, a missing factor, a thin narrative, weak evidence.

JSON shape:
{"changes": [{"objection_id": "O1", "action": "replace", "claim_id": "C4", "text": "..."}, {"objection_id": "O2", "action": "add", "section": "risks", "text": "..."}]}
