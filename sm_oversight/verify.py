"""Historical inspection of 0.1 oversight records, and the denying legacy gate.

0.1 gated execution on a category-level approval: the approval reviews this
action, a quorum of trusted humans witnessed it, and ARP's authority chain admits
the action under it. 0.2 moved permission to exact-action approvals
(``sm_oversight.exact.preflight`` + ``sm_oversight.executor.Executor.reserve``);
the 0.1 algorithm survives here as ``inspect_legacy`` — evidence about an old
record, never permission for a new privileged write — and ``verify_oversight``
remains only so that a caller still wired to the 0.1 gate fails closed instead of
failing open.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from sm_arp import verify_authority_chain, verify_receipt, verify_signature

from .context import APPROVED, OVERSIGHT_KEY
from .quorum import verify_quorum


@dataclass
class OversightResult:
    ok: bool
    # receipt | issuer | signature | not_approved | reviews_mismatch | quorum | authority
    # | legacy | legacy_denied | accepted — plus the stages ``exact`` returns.
    stage: str
    detail: str

    @classmethod
    def accepted(cls) -> OversightResult:
        return cls(True, "accepted", "action is human-approved with quorum")


def inspect_legacy(
    action: dict[str, Any],
    approval: dict[str, Any],
    *,
    required_m: int,
    trusted_reviewers: set[str],
) -> OversightResult:
    """Inspect a 0.1-style record: was ``action`` approved by ``approval`` with an
    M-of-N human quorum? Historical evidence only — never permission (SPEC §5).

    Stages, in order, rejecting at the first failure:

    1. ``receipt`` — ``approval`` is a valid ARP receipt (strict): its own issuer
       signature verifies. Witnesses co-sign the issuer-signed body, so a gesture
       whose issuer signature is garbage is rejected before any witness is counted.
    2. ``issuer`` — the gesture was issued by one of ``trusted_reviewers``.
    3. ``signature`` — the executed ``action``'s issuer signature verifies.
    4. ``not_approved`` — the gesture is an ``approved`` decision that reviewed a
       proposal (``reviews_receipt_id`` present).
    5. ``reviews_mismatch`` — ``action.granted_by_receipt_id`` equals
       ``approval.receipt_id`` (closing proposed → approved → executed).
    6. ``quorum`` — ≥ ``required_m`` distinct trusted reviewers witnessed the
       approval (``verify_quorum``).
    7. ``authority`` — ``sm_arp.verify_authority_chain`` admits ``action`` under
       ``approval`` (grant authenticated; scope, expiry, grantee, principal).
    """
    receipt = verify_receipt(approval)
    if not receipt.ok:
        return OversightResult(False, "receipt", f"approval receipt invalid: {receipt.detail}")
    if approval.get("issuer_did") not in trusted_reviewers:
        return OversightResult(False, "issuer", "approval was not issued by a trusted reviewer")
    if not verify_signature(action).ok:
        return OversightResult(False, "signature", "invalid execution signature")
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
        return OversightResult(False, q.stage, q.detail)

    a = verify_authority_chain(action, {approval["receipt_id"]: approval})
    if not a.ok:
        return OversightResult(False, "authority", a.detail)

    return OversightResult(True, "legacy", "legacy category evidence only")


def verify_oversight(
    action: dict[str, Any],
    approval: dict[str, Any],
    *,
    required_m: int,
    trusted_reviewers: set[str],
) -> OversightResult:
    """Deprecated 0.1 execution gate. Always denies.

    0.1 callers used this result as permission to execute; 0.2 withdrew that
    (README "Migration"). It is kept, denying, so a caller not yet migrated fails
    closed. It implements no algorithm — ``inspect_legacy`` carries the 0.1 stages
    as historical evidence, and ``exact.preflight`` + ``Executor.reserve`` are the
    permission-granting path. Scheduled for removal in 1.0.
    """
    warnings.warn(
        "sm_oversight.verify_oversight always denies; use sm_oversight.exact.preflight and "
        "Executor.reserve for permission, inspect_legacy for historical evidence",
        DeprecationWarning,
        stacklevel=2,
    )
    return OversightResult(
        False,
        "legacy_denied",
        "legacy gate denies execution; fresh exact-action approval required",
    )
