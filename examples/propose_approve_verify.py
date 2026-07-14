"""End-to-end oversight: propose -> 2-of-3 approve -> verify the gated action.

Runnable with just this package (+ sm-arp). The one gotcha this example exists
to teach: building the approval does NOT cast a quorum vote — every counting
reviewer signs via add_witness, INCLUDING the builder.
"""
import json
from sm_arp import Identity, build_action, issue_receipt
from sm_oversight import (
    APPROVED, add_witness, build_oversight_approval, verify_oversight, verify_quorum,
)

PRINCIPAL = "did:key:zPrincipal"

# The review panel (N=3) and the agent whose action needs sign-off.
r1, r2, r3 = (Identity.from_seed(bytes([b]) * 32) for b in (1, 2, 3))
agent = Identity.from_seed(bytes([9]) * 32)
trusted = {r1.did, r2.did, r3.did}

# 1. The agent PROPOSES a high-impact action (outcome pending).
proposal = issue_receipt(agent, principal_did=PRINCIPAL,
    action=build_action(category="memory_dissociation",
                        human_summary="exclude a poisoned memory segment",
                        outcome="pending"))

# 2. A reviewer builds the APPROVED gesture reviewing that proposal…
approval = build_oversight_approval(r1, principal_did=PRINCIPAL, agent_did=agent.did,
    reviews_receipt_id=proposal["receipt_id"], action_category="memory_dissociation",
    grant_expires_at="2099-01-01T00:00:00Z")
# …and BOTH counting reviewers sign as witnesses (the builder's receipt
# signature is NOT a quorum vote — r1 must add_witness too):
add_witness(approval, r1)
add_witness(approval, r2)

q = verify_quorum(approval, m=2, trusted=trusted)
print("quorum 2-of-3      :", q.ok, "| distinct trusted signers:", q.valid_count)

# 3. The agent EXECUTES, citing the approval; anyone verifies the whole gate.
executed = issue_receipt(agent, principal_did=PRINCIPAL,
    action=build_action(category="memory_dissociation",
                        human_summary="excluded the segment",
                        granted_by_receipt_id=approval["receipt_id"]))
result = verify_oversight(executed, approval, required_m=2, trusted_reviewers=trusted)
print("verify_oversight   :", result.ok, "| stage:", result.stage)

# The wire artifact, for the reference docs:
print("gesture envelope   :", json.dumps(approval["action"]["machine_payload"]["oversight"], sort_keys=True))
print("witness slot shape :", json.dumps(approval["evidence"]["witness_signatures"][0], sort_keys=True)[:120], "…")
