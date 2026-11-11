"""M-of-N quorum over an oversight gesture via ``evidence.witness_signatures``.

A gesture is signed by its issuing reviewer (the receipt ``signature``); a panel
adds co-signatures as ``evidence.witness_signatures`` — each an Ed25519 signature
over the gesture's canonical bytes EXCLUDING the witness list and the receipt
signature. Those are exactly the bytes the issuer signed: sm-arp >= 0.4 detaches
``evidence.witness_signatures`` from every byte commitment (issuer signature, chain
link, VRP corroboration), so this module reuses ``sm_arp.canonical_bytes`` rather
than restating the rule. One rule means a witness appended later never invalidates
the issuer signature, never moves the chain, and never breaks an earlier witness —
and an entry written here is byte-compatible with one written by
``sm_arp.vrp.cosign_receipt``.

Each entry is ``{"witness_did", "signature"}`` — ``witness_did`` is the ARP §5 key.
Entries written by sm-oversight < 0.3 carry ``signer_did`` instead; both are read.
A verifier first authenticates the gesture itself (``sm_arp.verify_receipt``,
strict), then requires ≥ M valid witness signatures from DISTINCT trusted
reviewers. The issuer's own receipt signature is never a vote.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from sm_arp import Identity, canonical_bytes, pubkey_from_did, verify_receipt

WITNESS_DID = "witness_did"
LEGACY_WITNESS_DID = "signer_did"


def witness_bytes(gesture: dict[str, Any]) -> bytes:
    """The bytes a witness signs: the gesture's issuer-signed body — JCS canonical,
    without ``signature`` and without ``evidence.witness_signatures``. Delegated to
    sm-arp so there is exactly one canonicalization rule."""
    return canonical_bytes(gesture, include_signature=False)


def witness_did(entry: dict[str, Any]) -> object:
    """The DID a witness entry names: ``witness_did`` (ARP §5), falling back to the
    pre-0.3 ``signer_did``. ``witness_did`` wins when both are present — the same
    precedence ``sm_arp.vrp`` applies, so the two readers never disagree."""
    return entry[WITNESS_DID] if WITNESS_DID in entry else entry.get(LEGACY_WITNESS_DID)


def add_witness(gesture: dict[str, Any], reviewer: Identity) -> dict[str, Any]:
    """Append ``reviewer``'s witness signature to the gesture (in place).

    The receipt's own ``signature`` is left untouched and keeps verifying: the
    witness list is detached evidence, outside the issuer's byte commitment.
    """
    sig = reviewer.sign(witness_bytes(gesture))
    evidence = gesture.setdefault("evidence", {})
    witnesses = evidence.setdefault("witness_signatures", [])
    witnesses.append(
        {WITNESS_DID: reviewer.did, "signature": base64.b64encode(sig).decode("ascii")}
    )
    return gesture


@dataclass
class QuorumResult:
    ok: bool
    stage: str  # receipt | quorum | accepted
    detail: str
    valid_count: int = 0


def verify_quorum(gesture: dict[str, Any], *, m: int, trusted: set[str]) -> QuorumResult:
    """True iff the gesture is a valid ARP receipt AND ≥ ``m`` distinct trusted
    reviewers have valid witness signatures over it.

    Witnesses co-sign the issuer-signed body, not the issuer's signature, so the
    receipt is authenticated first (``sm_arp.verify_receipt``, strict): a gesture
    whose issuer signature does not verify is rejected at stage ``receipt`` however
    many witnesses it carries. Nothing is trusted about the gesture's contents here
    beyond that; the gate (``verify.inspect_legacy``) checks who issued it.
    """
    if type(m) is not int or not 1 <= m <= len(trusted):
        return QuorumResult(False, "quorum", "invalid threshold")
    receipt = verify_receipt(gesture)
    if not receipt.ok:
        return QuorumResult(False, "receipt", f"gesture receipt invalid: {receipt.detail}")
    body = witness_bytes(gesture)
    seen: set[str] = set()
    valid = 0
    witnesses = gesture.get("evidence", {}).get("witness_signatures", [])
    for w in witnesses:
        if not isinstance(w, dict):
            continue
        did = witness_did(w)
        if not isinstance(did, str) or did in seen or did not in trusted:
            continue
        try:
            pubkey_from_did(did).verify(base64.b64decode(str(w["signature"]), validate=True), body)
        except (InvalidSignature, ValueError, KeyError, TypeError, binascii.Error):
            continue
        seen.add(did)
        valid += 1
    if valid >= m:
        return QuorumResult(True, "accepted", f"{valid} of {m} required signatures", valid)
    return QuorumResult(False, "quorum", f"only {valid} of {m} required trusted signatures", valid)


__all__ = [
    "LEGACY_WITNESS_DID",
    "WITNESS_DID",
    "QuorumResult",
    "add_witness",
    "verify_quorum",
    "witness_bytes",
    "witness_did",
]
