"""sm-oversight behavioural suite — gestures, M-of-N quorum, the oversight gate.

The suite IS the spec. The happy path is the full chain (agent proposes → 2-of-3
humans approve → agent executes → verifier confirms human-approval); every
rejection stage gets a hostile path.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sm_arp import Identity, build_action, issue_receipt

from sm_oversight import (
    DENIED,
    add_witness,
    build_oversight_approval,
    build_oversight_decision,
    verify_oversight,
    verify_quorum,
)


def _seed(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()


PRINCIPAL = Identity.from_seed(_seed("principal"))
AGENT = Identity.from_seed(_seed("agent"))
R1 = Identity.from_seed(_seed("reviewer-1"))
R2 = Identity.from_seed(_seed("reviewer-2"))
R3 = Identity.from_seed(_seed("reviewer-3"))
OUTSIDER = Identity.from_seed(_seed("outsider"))

TRUSTED = {R1.did, R2.did, R3.did}
FUTURE = "2099-01-01T00:00:00Z"
PRINCIPAL_DID = PRINCIPAL.did


def _proposal() -> dict[str, Any]:
    action = build_action(category="purchase", human_summary="propose buy", outcome="pending")
    return issue_receipt(AGENT, principal_did=PRINCIPAL_DID, action=action)


def _approval(proposal: dict[str, Any], witnesses: list[Identity]) -> dict[str, Any]:
    appr = build_oversight_approval(
        R1,
        principal_did=PRINCIPAL_DID,
        agent_did=AGENT.did,
        reviews_receipt_id=proposal["receipt_id"],
        action_category="purchase",
        grant_expires_at=FUTURE,
    )
    for w in witnesses:
        add_witness(appr, w)
    return appr


def _executed(approval: dict[str, Any]) -> dict[str, Any]:
    action = build_action(
        category="purchase",
        human_summary="execute buy",
        granted_by_receipt_id=approval["receipt_id"],
    )
    return issue_receipt(AGENT, principal_did=PRINCIPAL_DID, action=action)


# ── happy path ─────────────────────────────────────────────────────


def test_full_chain_2_of_3_approved() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2])  # 2 witnesses
    executed = _executed(approval)
    res = verify_oversight(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert res.ok and res.stage == "accepted"


# ── quorum ─────────────────────────────────────────────────────────


def test_quorum_not_met() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1])  # only 1 witness, need 2
    executed = _executed(approval)
    res = verify_oversight(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "quorum"


def test_untrusted_witness_does_not_count() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, OUTSIDER])  # outsider not in TRUSTED
    executed = _executed(approval)
    res = verify_oversight(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "quorum"  # only 1 trusted


def test_duplicate_signer_counts_once() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R1])  # same reviewer twice
    executed = _executed(approval)
    res = verify_oversight(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "quorum"  # de-duped to 1


def test_forged_witness_signature_rejected() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2])
    approval["evidence"]["witness_signatures"][1]["signature"] = "AA=="  # corrupt R2's sig
    q = verify_quorum(approval, m=2, trusted=TRUSTED)
    assert not q.ok and q.valid_count == 1


# ── gate stages ────────────────────────────────────────────────────


def test_not_approved_when_denied_gesture() -> None:
    proposal = _proposal()
    denial = build_oversight_decision(
        R1, decision=DENIED, principal_did=PRINCIPAL_DID, reviews_receipt_id=proposal["receipt_id"]
    )
    add_witness(denial, R1)
    add_witness(denial, R2)
    executed = _executed(denial)  # agent tries to execute citing a DENIAL
    res = verify_oversight(executed, denial, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "not_approved"


def test_action_not_referencing_approval_rejected() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2])
    # executed action with NO granted_by linking to the approval
    rogue = issue_receipt(
        AGENT,
        principal_did=PRINCIPAL_DID,
        action=build_action(category="purchase", human_summary="rogue"),
    )
    res = verify_oversight(rogue, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "reviews_mismatch"


def test_authority_scope_mismatch_rejected() -> None:
    # Approval scoped to "purchase"; agent executes a "payment_sent" citing it.
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2])
    action = build_action(
        category="payment_sent",
        human_summary="out of scope",
        granted_by_receipt_id=approval["receipt_id"],
    )
    executed = issue_receipt(AGENT, principal_did=PRINCIPAL_DID, action=action)
    res = verify_oversight(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "authority"
