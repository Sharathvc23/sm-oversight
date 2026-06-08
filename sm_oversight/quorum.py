"""M-of-N quorum over an oversight gesture via ``evidence.witness_signatures``.

A gesture is signed by its issuing reviewer (the receipt ``signature``); a panel
adds co-signatures as ``evidence.witness_signatures`` — each an Ed25519 signature
over the gesture's canonical bytes EXCLUDING the witness list and the receipt
signature (so adding a witness never changes what earlier witnesses signed). A
verifier requires ≥ M valid signatures from DISTINCT trusted reviewers.

This formalizes the M-of-N countersignature pattern as a protocol artifact.
"""

from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
from typing import Any

import jcs
from cryptography.exceptions import InvalidSignature
from sm_arp import Identity, pubkey_from_did


def _quorum_bytes(gesture: dict[str, Any]) -> bytes:
    """Canonical bytes a witness signs: the gesture without its ``signature`` and
    without ``evidence.witness_signatures`` (those are added by signing)."""
    g = copy.deepcopy(gesture)
    g.pop("signature", None)
    ev = g.get("evidence")
    if isinstance(ev, dict):
        ev.pop("witness_signatures", None)
        if not ev:
            g.pop("evidence", None)
    return bytes(jcs.canonicalize(g))


def add_witness(gesture: dict[str, Any], reviewer: Identity) -> dict[str, Any]:
    """Append ``reviewer``'s witness signature to the gesture (in place)."""
    sig = reviewer.sign(_quorum_bytes(gesture))
    evidence = gesture.setdefault("evidence", {})
    witnesses = evidence.setdefault("witness_signatures", [])
    witnesses.append(
        {"signer_did": reviewer.did, "signature": base64.b64encode(sig).decode("ascii")}
    )
    return gesture


@dataclass
class QuorumResult:
    ok: bool
    stage: str  # quorum | accepted
    detail: str
    valid_count: int = 0


def verify_quorum(gesture: dict[str, Any], *, m: int, trusted: set[str]) -> QuorumResult:
    """True iff ≥ ``m`` distinct trusted reviewers have valid witness signatures."""
    body = _quorum_bytes(gesture)
    seen: set[str] = set()
    valid = 0
    witnesses = gesture.get("evidence", {}).get("witness_signatures", [])
    for w in witnesses:
        did = w.get("signer_did")
        if not isinstance(did, str) or did in seen or did not in trusted:
            continue
        try:
            pubkey_from_did(did).verify(base64.b64decode(w["signature"]), body)
        except (InvalidSignature, ValueError, KeyError):
            continue
        seen.add(did)
        valid += 1
    if valid >= m:
        return QuorumResult(True, "accepted", f"{valid} of {m} required signatures", valid)
    return QuorumResult(False, "quorum", f"only {valid} of {m} required trusted signatures", valid)


__all__ = ["QuorumResult", "add_witness", "verify_quorum"]
