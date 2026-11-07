"""Local owner review command using a separately held encrypted Ed25519 PEM."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sm_arp import Identity, chain_link, verify_receipt

from .exact import Policy, Receipt, decide, preflight, vote
from .wire import parse_bundle


def review(proposal: Receipt, policy: Policy) -> str:
    if not verify_receipt(proposal).ok:
        raise ValueError("invalid proposal signature")
    action = proposal["action"]
    payload = action["machine_payload"]
    if (
        proposal["issuer_did"] != policy.agent
        or proposal["principal_did"] != policy.principal
        or action["category"] != "other"
        or action["outcome"] != "pending"
        or payload.get("version") != "sm-oversight/0.2"
        or payload.get("policy") != policy.digest()
        or set(payload) != {"version", "request", "policy"}
    ):
        raise ValueError("proposal outside local policy")
    return json.dumps(
        {
            "operation": policy.operation,
            "executor": policy.executor,
            "request": payload["request"],
            "proposal": chain_link(proposal),
        },
        indent=2,
        ensure_ascii=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("policy", type=Path, help="locally installed policy JSON")
    parser.add_argument("key", type=Path, help="encrypted Ed25519 private key in PEM format")
    parser.add_argument("--output", type=Path, required=True, help="new private evidence file")
    parser.add_argument("--cosign", type=Path, help="existing panel decision bundle")
    args = parser.parse_args()
    proposal = parse_bundle(args.proposal.read_bytes())
    config = parse_bundle(args.policy.read_bytes())
    policy = Policy(**{**config, "reviewers": tuple(config["reviewers"])})
    if not sys.stdin.isatty():
        parser.error("interactive owner terminal required")
    print(review(proposal, policy), file=sys.stderr)
    existing = parse_bundle(args.cosign.read_bytes()) if args.cosign else None
    choices = {"approve", "deny", "escalate", "request_changes"}
    if existing is not None:
        if existing["proposal"] != proposal:
            parser.error("panel bundle refers to a different proposal")
        checked = preflight(
            proposal,
            existing["decision"],
            existing["votes"],
            policy,
            proposal["action"]["machine_payload"]["request"],
            at=datetime.now(UTC),
        )
        if checked.detail != "insufficient votes":
            parser.error("expected a valid approval awaiting additional votes")
        choices = {"approve"}
    print("Enter a decision: " + ", ".join(sorted(choices)), file=sys.stderr)
    choice = input()
    if choice not in choices:
        raise SystemExit("Review cancelled")
    key = serialization.load_pem_private_key(
        args.key.read_bytes(), password=getpass.getpass("Owner key passphrase: ").encode()
    )
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("expected Ed25519 owner key")
    owner = Identity.from_seed(key.private_bytes_raw())
    if owner.did not in policy.reviewers:
        raise ValueError("key is not enrolled under local policy")
    expiry = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    decision = (
        existing["decision"]
        if existing
        else decide(owner, proposal, policy, decision=choice, expires=expiry)
    )
    votes = list(existing["votes"]) if existing else []
    if any(entry["signer"] == owner.did for entry in votes):
        parser.error("reviewer already signed this decision")
    votes.append(vote(owner, decision))
    data = json.dumps({"proposal": proposal, "decision": decision, "votes": votes})
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(data + "\n")


if __name__ == "__main__":
    main()
