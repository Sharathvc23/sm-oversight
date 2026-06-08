"""The oversight gate — was this action human-approved with quorum?

Composes the three checks that make an executed action defensible under EU AI Act
Art. 14: the approval actually reviews this action, a quorum of trusted humans
signed it, and ARP's authority chain admits the action under that approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sm_arp import verify_authority_chain

from .context import APPROVED, OVERSIGHT_KEY
from .quorum import verify_quorum


@dataclass
class OversightResult:
    ok: bool
    # not_approved | reviews_mismatch | quorum | authority | accepted
    stage: str
    detail: str

    @classmethod
    def accepted(cls) -> OversightResult:
        return cls(True, "accepted", "action is human-approved with quorum")


def verify_oversight(
    action: dict[str, Any],
    approval: dict[str, Any],
    *,
    required_m: int,
    trusted_reviewers: set[str],
) -> OversightResult:
    """Verify ``action`` was approved by ``approval`` with an M-of-N human quorum.

    1. ``approval`` is an approve gesture that reviewed a proposal, and the
       executed ``action`` references it via ``granted_by_receipt_id`` (closing the
       proposed → approval → executed chain); 2. ≥ ``required_m`` distinct trusted
       reviewers witnessed the approval; 3. ARP's authority chain admits ``action``
       under ``approval`` (scope, expiry, grantee, principal).
    """
    osp = approval.get("action", {}).get("machine_payload", {}).get(OVERSIGHT_KEY, {})
    if osp.get("decision") != APPROVED:
        return OversightResult(
            False, "not_approved", "approval gesture is not an 'approved' decision"
        )
    if not osp.get("reviews_receipt_id"):
        return OversightResult(
            False, "not_approved", "approval reviewed no proposal (missing reviews_receipt_id)"
        )

    if action.get("action", {}).get("granted_by_receipt_id") != approval.get("receipt_id"):
        return OversightResult(False, "reviews_mismatch", "action does not reference this approval")

    q = verify_quorum(approval, m=required_m, trusted=trusted_reviewers)
    if not q.ok:
        return OversightResult(False, "quorum", q.detail)

    a = verify_authority_chain(action, {approval["receipt_id"]: approval})
    if not a.ok:
        return OversightResult(False, "authority", a.detail)

    return OversightResult.accepted()


__all__ = ["OversightResult", "verify_oversight"]
