"""Local owner review command using a separately held encrypted Ed25519 PEM."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sm_arp import Identity, chain_link, verify_receipt

from .exact import Policy, Receipt, decide, vote
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
    args = parser.parse_args()
    proposal = parse_bundle(args.proposal.read_bytes())
    config = parse_bundle(args.policy.read_bytes())
    policy = Policy(**{**config, "reviewers": tuple(config["reviewers"])})
    if not sys.stdin.isatty():
        parser.error("interactive owner terminal required")
    print(review(proposal, policy), file=sys.stderr)
    print("Type approve to sign a five-minute approval, or press Enter to cancel.", file=sys.stderr)
    if input() != "approve":
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
    decision = decide(owner, proposal, policy, decision="approve", expires=expiry)
    print(
        json.dumps({"proposal": proposal, "decision": decision, "votes": [vote(owner, decision)]})
    )


if __name__ == "__main__":
    main()
