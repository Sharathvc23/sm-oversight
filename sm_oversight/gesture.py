"""Build human-oversight gesture receipts (approve / deny / escalate).

Each gesture is a signed ARP receipt issued by the human reviewer. The approve
gesture is an ``authority_granted`` receipt so it plugs straight into ARP's
authority chain (the executed action references it via ``granted_by_receipt_id``
and ``sm_arp.verify_authority_chain`` enforces "human-approved"). Deny and
escalate are ``decision_made`` receipts — auditable override records. All three
carry an oversight envelope under ``action.machine_payload.oversight``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sm_arp import Identity, build_action, issue_receipt

from .context import APPROVED, DENIED, ESCALATED, OVERSIGHT_KEY


def _require_rfc3339(grant_expires_at: str) -> None:
    """Reject an expiry ``sm_arp.verify_authority_chain`` would later fail: it must be
    an RFC 3339 timestamp carrying a UTC offset (``Z`` or ``±hh:mm``). A naive or
    unparseable value would sign a grant that no verifier admits."""
    if not isinstance(grant_expires_at, str) or not grant_expires_at:
        raise ValueError("grant_expires_at must be a non-empty RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(grant_expires_at)
    except ValueError as exc:
        raise ValueError(f"grant_expires_at is not RFC 3339: {grant_expires_at!r}") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"grant_expires_at must carry a UTC offset: {grant_expires_at!r}")


def build_oversight_approval(
    reviewer: Identity,
    *,
    principal_did: str,
    agent_did: str,
    reviews_receipt_id: str,
    action_category: str,
    grant_expires_at: str,
    reviewers: list[str] | None = None,
    human_summary: str = "",
) -> dict[str, Any]:
    """An ``authority_granted`` receipt approving one proposed action.

    Scoped to ``action_category`` for ``agent_did`` until ``grant_expires_at`` —
    so ``sm_arp.verify_authority_chain`` admits the executed action that points at
    it. ``reviews_receipt_id`` is the proposed action receipt being reviewed.

    ``grant_expires_at`` must be an RFC 3339 timestamp with a UTC offset; anything
    else raises ``ValueError`` here rather than failing at verification.

    ``reviewers`` is informational metadata asserted by the issuer: it names who
    was asked to review, and nothing checks it. Quorum is over
    ``evidence.witness_signatures`` only — every counted reviewer must
    ``add_witness`` (the issuer included). Nobody listed here has signed anything.
    """
    _require_rfc3339(grant_expires_at)
    machine_payload: dict[str, Any] = {
        "granted_scope": [action_category],
        "granted_to_did": agent_did,
        "grant_expires_at": grant_expires_at,
        OVERSIGHT_KEY: {
            "decision": APPROVED,
            "reviews_receipt_id": reviews_receipt_id,
            "reviewers": reviewers or [reviewer.did],
        },
    }
    action = build_action(
        category="authority_granted",
        human_summary=human_summary or f"Approved {action_category} for {agent_did[:24]}…",
        machine_payload=machine_payload,
    )
    receipt: dict[str, Any] = issue_receipt(reviewer, principal_did=principal_did, action=action)
    return receipt


def build_oversight_decision(
    reviewer: Identity,
    *,
    decision: str,
    principal_did: str,
    reviews_receipt_id: str,
    reviewers: list[str] | None = None,
    human_summary: str = "",
) -> dict[str, Any]:
    """A ``decision_made`` receipt recording a deny or escalate gesture.

    ``reviewers`` is informational, issuer-asserted metadata, exactly as in
    ``build_oversight_approval``: quorum counts ``evidence.witness_signatures``.
    """
    if decision not in (DENIED, ESCALATED):
        raise ValueError(
            f"decision must be {DENIED!r} or {ESCALATED!r}; use build_oversight_approval to approve"
        )
    machine_payload: dict[str, Any] = {
        OVERSIGHT_KEY: {
            "decision": decision,
            "reviews_receipt_id": reviews_receipt_id,
            "reviewers": reviewers or [reviewer.did],
        },
    }
    action = build_action(
        category="decision_made",
        human_summary=human_summary or f"Oversight {decision} of {reviews_receipt_id[:8]}…",
        machine_payload=machine_payload,
    )
    receipt: dict[str, Any] = issue_receipt(reviewer, principal_did=principal_did, action=action)
    return receipt


__all__ = ["build_oversight_approval", "build_oversight_decision"]
