"""Exact-action approvals. Policy and outgoing requests come from the relying party."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import jcs
from cryptography.exceptions import InvalidSignature
from sm_arp import (
    Identity,
    build_action,
    chain_link,
    issue_receipt,
    pubkey_from_did,
    verify_receipt,
)

from .verify import OversightResult

Receipt = dict[str, Any]
VERSION = "sm-oversight/0.2"


def _digest(value: Any) -> str:
    return hashlib.sha256(jcs.canonicalize(value)).hexdigest()


@dataclass(frozen=True)
class Policy:
    principal: str
    agent: str
    executor: str
    operation: str
    reviewers: tuple[str, ...]
    threshold: int
    revision: str

    def __post_init__(self) -> None:
        if type(self.threshold) is not int or not 1 <= self.threshold <= len(self.reviewers):
            raise ValueError("invalid threshold")
        if len(set(self.reviewers)) != len(self.reviewers):
            raise ValueError("duplicate reviewer")
        if not all((self.principal, self.agent, self.executor, self.operation, self.revision)):
            raise ValueError("missing policy authority or operation")
        for reviewer in self.reviewers:
            pubkey_from_did(reviewer)

    def digest(self) -> str:
        return _digest({**vars(self), "reviewers": sorted(self.reviewers)})


def propose(agent: Identity, policy: Policy, request: Receipt, *, summary: str) -> Receipt:
    if agent.did != policy.agent:
        raise ValueError("wrong agent")
    return issue_receipt(
        agent,
        principal_did=policy.principal,
        action=build_action(
            category="other",
            outcome="pending",
            human_summary=summary,
            machine_payload={"version": VERSION, "policy": policy.digest(), "request": request},
        ),
    )


def decide(
    reviewer: Identity, proposal: Receipt, policy: Policy, *, decision: str, expires: str
) -> Receipt:
    if decision not in {"approve", "deny", "escalate", "request_changes"}:
        raise ValueError("unknown decision")
    return issue_receipt(
        reviewer,
        principal_did=policy.principal,
        action=build_action(
            category="decision_made",
            human_summary=decision,
            machine_payload={
                "version": VERSION,
                "proposal": chain_link(proposal),
                "policy": policy.digest(),
                "decision": decision,
                "expires": expires,
            },
        ),
    )


def _vote_bytes(decision: Receipt, signer: str) -> bytes:
    return b"sm-oversight/0.2/vote\x00" + bytes(
        jcs.canonicalize({"decision_digest": chain_link(decision), "signer": signer})
    )


def vote(signer: Identity, decision: Receipt) -> dict[str, str]:
    return {
        "signer": signer.did,
        "signature": base64.b64encode(signer.sign(_vote_bytes(decision, signer.did))).decode(
            "ascii"
        ),
    }


def preflight(
    proposal: Receipt,
    decision: Receipt,
    votes: list[dict[str, str]],
    policy: Policy,
    outgoing: Receipt,
    *,
    at: datetime,
) -> OversightResult:
    """Authenticate a bundle against local policy and final request. Reservation is separate."""
    try:
        for item in (proposal, decision):
            result = verify_receipt(item)
            if not result.ok or item["principal_did"] != policy.principal:
                return OversightResult(False, "receipt", "invalid receipt or principal")
        proposed = proposal["action"]
        reviewed = decision["action"]
        intent = proposed["machine_payload"]
        choice = reviewed["machine_payload"]
        if (
            proposal["issuer_did"] != policy.agent
            or proposed["category"] != "other"
            or proposed["outcome"] != "pending"
            or reviewed["category"] != "decision_made"
            or reviewed["outcome"] != "completed"
            or decision["issuer_did"] not in policy.reviewers
            or choice["decision"] != "approve"
        ):
            return OversightResult(False, "authority", "unexpected issuer or decision")
        if (
            intent != {"version": VERSION, "policy": policy.digest(), "request": outgoing}
            or _digest(intent["request"]) != _digest(outgoing)
            or choice
            != {
                "version": VERSION,
                "policy": policy.digest(),
                "decision": "approve",
                "proposal": chain_link(proposal),
                "expires": choice["expires"],
            }
        ):
            return OversightResult(False, "intent", "proposal, policy or request mismatch")
        if not (
            datetime.fromisoformat(proposal["issued_at"])
            <= datetime.fromisoformat(decision["issued_at"])
            <= at
            < datetime.fromisoformat(choice["expires"])
        ):
            return OversightResult(False, "time", "outside validity interval")
        signers = set()
        if len(votes) > len(policy.reviewers):
            return OversightResult(False, "quorum", "too many votes")
        for entry in votes:
            signer = entry["signer"]
            if signer not in policy.reviewers or signer in signers:
                return OversightResult(False, "quorum", "ineligible or repeated reviewer")
            pubkey_from_did(signer).verify(
                base64.b64decode(entry["signature"], validate=True), _vote_bytes(decision, signer)
            )
            signers.add(signer)
        if len(signers) < policy.threshold:
            return OversightResult(False, "quorum", "insufficient votes")
    except (
        InvalidSignature,
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        return OversightResult(False, "evidence", "malformed or invalid evidence")
    return OversightResult(True, "verified", "exact request approved")


def record_outcome(
    executor: Identity,
    policy: Policy,
    proposal: Receipt,
    decision: Receipt,
    outgoing: Receipt,
    *,
    state: str,
    provider_ref: str,
) -> Receipt:
    """Sign the executor's observation. Provider evidence can be retained separately."""
    if executor.did != policy.executor or state not in {"succeeded", "failed", "unknown"}:
        raise ValueError("invalid executor or state")
    return issue_receipt(
        executor,
        principal_did=policy.principal,
        action=build_action(
            category="attestation_issued",
            human_summary=state,
            machine_payload={
                "version": VERSION,
                "proposal": chain_link(proposal),
                "decision": chain_link(decision),
                "request_digest": _digest(outgoing),
                "state": state,
                "provider_ref": provider_ref,
            },
        ),
    )


def inspect_outcome(
    outcome: Receipt,
    proposal: Receipt,
    decision: Receipt,
    votes: list[dict[str, str]],
    policy: Policy,
    outgoing: Receipt,
    *,
    reserved_at: datetime,
) -> OversightResult:
    """reserved_at must come from the executor's trusted reservation history."""
    checked = preflight(proposal, decision, votes, policy, outgoing, at=reserved_at)
    if not checked.ok:
        return checked
    try:
        evidence = outcome["action"]["machine_payload"]
        if (
            verify_receipt(outcome).ok
            and outcome["issuer_did"] == policy.executor
            and outcome["principal_did"] == policy.principal
            and outcome["action"]["category"] == "attestation_issued"
            and outcome["action"]["outcome"] == "completed"
            and datetime.fromisoformat(outcome["issued_at"]) >= reserved_at.replace(microsecond=0)
            and evidence["version"] == VERSION
            and evidence["proposal"] == chain_link(proposal)
            and evidence["decision"] == chain_link(decision)
            and evidence["request_digest"] == _digest(outgoing)
            and evidence["state"] in {"succeeded", "failed", "unknown"}
        ):
            return OversightResult(True, evidence["state"], "executor attestation verified")
    except (KeyError, TypeError, AttributeError, ValueError, RecursionError, OverflowError):
        pass
    return OversightResult(False, "outcome", "invalid executor evidence")
