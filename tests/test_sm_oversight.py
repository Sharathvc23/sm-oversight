"""sm-oversight behavioural suite — gestures, M-of-N quorum, the oversight gate.

The suite IS the spec. The happy path is the full chain (agent proposes → 2-of-3
humans approve → agent executes → verifier confirms human-approval); every
rejection stage gets a hostile path.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

import pytest
from sm_arp import (
    Identity,
    build_action,
    canonical_bytes,
    chain_link,
    issue_receipt,
    verify_receipt,
)
from sm_arp.vrp import cosign_receipt, is_corroborated

from sm_oversight import (
    DENIED,
    add_witness,
    build_oversight_approval,
    build_oversight_decision,
    verify_oversight,
    verify_quorum,
)
from sm_oversight.quorum import witness_bytes
from sm_oversight.verify import inspect_legacy


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
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert res.ok and res.stage == "legacy"


# ── quorum ─────────────────────────────────────────────────────────


def test_quorum_not_met() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1])  # only 1 witness, need 2
    executed = _executed(approval)
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "quorum"


def test_untrusted_witness_does_not_count() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, OUTSIDER])  # outsider not in TRUSTED
    executed = _executed(approval)
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "quorum"  # only 1 trusted


def test_duplicate_signer_counts_once() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R1])  # same reviewer twice
    executed = _executed(approval)
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
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
    res = inspect_legacy(executed, denial, required_m=2, trusted_reviewers=TRUSTED)
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
    res = inspect_legacy(rogue, approval, required_m=2, trusted_reviewers=TRUSTED)
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
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "authority"


# ── gesture receipt authentication (audit 2026-11) ─────────────────


def test_cosigned_gesture_still_verifies_as_arp_receipt() -> None:
    """Witnessing is detached evidence: the issuer signature and the chain link of
    a gesture are unchanged by add_witness (sm-arp >= 0.4 shares one rule)."""
    proposal = _proposal()
    approval = _approval(proposal, [])
    link_before = chain_link(approval)
    sig_before = approval["signature"]
    for w in (R1, R2, R3):
        add_witness(approval, w)
    assert approval["signature"] == sig_before
    assert chain_link(approval) == link_before
    assert verify_receipt(approval).ok  # strict
    assert verify_quorum(approval, m=3, trusted=TRUSTED).ok
    assert all(w["witness_did"] in TRUSTED for w in approval["evidence"]["witness_signatures"])


def test_witness_bytes_are_the_issuer_signed_bytes() -> None:
    approval = _approval(_proposal(), [R1, R2])
    assert witness_bytes(approval) == canonical_bytes(approval, include_signature=False)


def test_garbage_issuer_signature_rejected_despite_full_quorum() -> None:
    """An approval whose own receipt signature is zeros but which carries three
    valid witnesses is NOT a valid gesture — the receipt is authenticated first."""
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2, R3])
    approval["signature"] = base64.b64encode(bytes(64)).decode("ascii")
    executed = _executed(approval)
    q = verify_quorum(approval, m=3, trusted=TRUSTED)
    assert not q.ok and q.stage == "receipt" and q.valid_count == 0
    res = inspect_legacy(executed, approval, required_m=3, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "receipt"


def test_tampered_gesture_payload_rejected_despite_full_quorum() -> None:
    """Changing the grantee after issuance breaks the issuer signature; the witnesses
    (who signed the original body) are never consulted."""
    approval = _approval(_proposal(), [R1, R2, R3])
    approval["action"]["machine_payload"]["granted_to_did"] = OUTSIDER.did
    q = verify_quorum(approval, m=2, trusted=TRUSTED)
    assert not q.ok and q.stage == "receipt"


def test_gesture_issued_by_untrusted_reviewer_rejected() -> None:
    proposal = _proposal()
    approval = build_oversight_approval(
        OUTSIDER,
        principal_did=PRINCIPAL_DID,
        agent_did=AGENT.did,
        reviews_receipt_id=proposal["receipt_id"],
        action_category="purchase",
        grant_expires_at=FUTURE,
    )
    add_witness(approval, R1)
    add_witness(approval, R2)
    executed = _executed(approval)
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "issuer"


def test_corrupted_execution_signature_rejected() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2])
    executed = {**_executed(approval), "signature": "AA=="}
    res = inspect_legacy(executed, approval, required_m=2, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "signature"


def test_issuer_signature_cannot_be_attributed_to_another_reviewer() -> None:
    """Witnesses sign the issuer-signed bytes (one rule, sm-arp >= 0.4), so the
    issuer's receipt signature is byte-identical to their own add_witness entry and
    counts once, under the issuer's DID. Copied under any OTHER DID it is rejected —
    a signature never moves between reviewers."""
    approval = _approval(_proposal(), [R2])
    approval["evidence"]["witness_signatures"].append(
        {"witness_did": R3.did, "signature": approval["signature"]}
    )
    q = verify_quorum(approval, m=2, trusted=TRUSTED)
    assert not q.ok and q.stage == "quorum" and q.valid_count == 1
    approval["evidence"]["witness_signatures"].append(
        {"witness_did": R1.did, "signature": approval["signature"]}
    )
    add_witness(approval, R1)  # deterministic Ed25519: same bytes as the receipt signature
    assert approval["evidence"]["witness_signatures"][-1]["signature"] == approval["signature"]
    assert verify_quorum(approval, m=2, trusted=TRUSTED).valid_count == 2  # R1 once, R2 once


def test_invalid_threshold_rejected() -> None:
    approval = _approval(_proposal(), [R1, R2, R3])
    for m in (0, -1, 4, True):
        q = verify_quorum(approval, m=m, trusted=TRUSTED)  # type: ignore[arg-type]
        assert not q.ok and q.stage == "quorum"


# ── witness entry key: witness_did written, signer_did still read ──


def test_add_witness_writes_witness_did() -> None:
    approval = _approval(_proposal(), [R1])
    (entry,) = approval["evidence"]["witness_signatures"]
    assert set(entry) == {"witness_did", "signature"}
    assert entry["witness_did"] == R1.did


def test_legacy_signer_did_entries_still_count() -> None:
    """Records witnessed by sm-oversight < 0.3 wrote signer_did; they still verify."""
    approval = _approval(_proposal(), [R1, R2])
    for entry in approval["evidence"]["witness_signatures"]:
        entry["signer_did"] = entry.pop("witness_did")
    q = verify_quorum(approval, m=2, trusted=TRUSTED)
    assert q.ok and q.valid_count == 2


def test_witness_did_wins_over_signer_did_when_both_present() -> None:
    approval = _approval(_proposal(), [R1])
    (entry,) = approval["evidence"]["witness_signatures"]
    entry["signer_did"] = R2.did  # alias naming someone else: ignored, same as sm_arp.vrp
    q = verify_quorum(approval, m=1, trusted=TRUSTED)
    assert q.ok and q.valid_count == 1
    assert not verify_quorum(approval, m=1, trusted={R2.did}).ok


def test_vrp_cosign_entry_counts_toward_quorum() -> None:
    """Interop: an entry produced by sm_arp.vrp.cosign_receipt is a quorum vote."""
    approval = _approval(_proposal(), [R1])
    approval["evidence"]["witness_signatures"].append(
        cosign_receipt(approval, signing_key_bytes=R2.sk_bytes)
    )
    q = verify_quorum(approval, m=2, trusted=TRUSTED)
    assert q.ok and q.valid_count == 2


def test_add_witness_entry_corroborates_under_vrp() -> None:
    """Interop: add_witness by the counterparty satisfies sm_arp.vrp.is_corroborated,
    so one witness list serves both quorum and corroboration."""
    action = build_action(
        category="authority_granted",
        human_summary="approve",
        counterparty_did=R2.did,
        machine_payload={
            "granted_scope": ["purchase"],
            "granted_to_did": AGENT.did,
            "grant_expires_at": FUTURE,
            "oversight": {"decision": "approved", "reviews_receipt_id": "x", "reviewers": []},
        },
    )
    approval = issue_receipt(R1, principal_did=PRINCIPAL_DID, action=action)
    assert not is_corroborated(approval)
    add_witness(approval, R2)
    assert is_corroborated(approval)
    assert verify_quorum(approval, m=1, trusted=TRUSTED).ok


# ── gesture construction ──────────────────────────────────────────


@pytest.mark.parametrize(
    "expiry", ["", "tomorrow", "2099-01-01", "2099-01-01T00:00:00", "2099-13-01T00:00:00Z"]
)
def test_build_approval_rejects_non_rfc3339_expiry(expiry: str) -> None:
    with pytest.raises(ValueError):
        build_oversight_approval(
            R1,
            principal_did=PRINCIPAL_DID,
            agent_did=AGENT.did,
            reviews_receipt_id="x",
            action_category="purchase",
            grant_expires_at=expiry,
        )


def test_build_approval_accepts_offset_expiry() -> None:
    approval = build_oversight_approval(
        R1,
        principal_did=PRINCIPAL_DID,
        agent_did=AGENT.did,
        reviews_receipt_id="x",
        action_category="purchase",
        grant_expires_at="2099-01-01T00:00:00+02:00",
    )
    assert verify_receipt(approval).ok


def test_reviewers_list_is_not_a_vote() -> None:
    """Naming the whole panel in `reviewers` signs nothing; quorum is witnesses only."""
    approval = build_oversight_approval(
        R1,
        principal_did=PRINCIPAL_DID,
        agent_did=AGENT.did,
        reviews_receipt_id="x",
        action_category="purchase",
        grant_expires_at=FUTURE,
        reviewers=sorted(TRUSTED),
    )
    q = verify_quorum(approval, m=1, trusted=TRUSTED)
    assert not q.ok and q.valid_count == 0


def test_legacy_gate_always_denies() -> None:
    proposal = _proposal()
    approval = _approval(proposal, [R1, R2, R3])
    executed = _executed(approval)
    assert inspect_legacy(executed, approval, required_m=3, trusted_reviewers=TRUSTED).ok
    with pytest.warns(DeprecationWarning):
        res = verify_oversight(executed, approval, required_m=3, trusted_reviewers=TRUSTED)
    assert not res.ok and res.stage == "legacy_denied"
