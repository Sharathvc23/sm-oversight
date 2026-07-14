# sm-oversight

**Human oversight protocol — signed approve/deny/escalate gestures with M-of-N quorum, as an auditable ARP receipt chain**

EU AI Act Article 14 requires human oversight capabilities for high-risk AI. One
mechanism that supports that duty — and that we found no open protocol for — is turning
a human's approve/deny/escalate into a **signed, verifiable override record**.
sm-oversight is that mechanism. A reviewer's gesture is an ARP receipt; an
approval is an *authority grant* for the specific proposed action, so the agent's
executed receipt references it and ARP's authority chain proves the action was
human-approved. Panels are supported via M-of-N witness signatures.

The chain it produces:

```
agent proposes (outcome="pending")  →  humans review (approve/deny/escalate gesture,
                                        M-of-N co-signed)  →  agent executes
                                        (granted_by_receipt_id → the approval)
```

The one thing sm-oversight owns: the **oversight gesture + quorum + the gate** that
confirms an action was human-approved. Receipts and the authority chain are ARP's.

## What this package secures (v0.1)

- **Signed gestures.** approve → an `authority_granted` ARP receipt; deny / escalate →
  `decision_made` receipts. All carry an oversight envelope.
- **M-of-N quorum.** A panel co-signs via `evidence.witness_signatures`; the gate
  requires ≥ M valid signatures from distinct trusted reviewers.
- **Provable human-approval.** `verify_oversight` composes: the executed action
  references the approval, quorum is met, and ARP's authority chain admits the action
  (scope, expiry, grantee).
- **Adversarially tested.** quorum-not-met, untrusted witness, duplicate signer,
  forged witness signature, deny-cited-as-approval, action-not-referencing-approval,
  out-of-scope authority.

## What this package does NOT do

- **Run the reviewer UI / routing.** sm-oversight records and verifies the gesture;
  the panel surface (e.g. a decision inspector) is the consumer's emitter.
- **First-class `oversight_*` ARP categories.** v0.1 rides on existing categories +
  a `machine_payload` envelope; promoting to dedicated categories is a future additive
  ARP change.

## Installation

```bash
pip install sm-oversight    # requires sm-arp>=0.1
```

## Quick start

```python
from sm_arp import Identity, build_action, issue_receipt
from sm_oversight import build_oversight_approval, add_witness, verify_oversight

P = "did:key:zPrincipal"                                    # the accountable principal
r1, r2, r3 = (Identity.from_seed(bytes([b]) * 32) for b in (1, 2, 3))   # the review panel
agent = Identity.from_seed(bytes([9]) * 32)

# 1. agent proposes
proposal = issue_receipt(agent, principal_did=P,
                         action=build_action(category="purchase", human_summary="buy", outcome="pending"))

# 2. a 2-of-3 human panel approves (the approval is an authority grant for the action)
approval = build_oversight_approval(r1, principal_did=P, agent_did=agent.did,
                                    reviews_receipt_id=proposal["receipt_id"],
                                    action_category="purchase", grant_expires_at="2099-01-01T00:00:00Z")
add_witness(approval, r1); add_witness(approval, r2)

# 3. agent executes, citing the approval
executed = issue_receipt(agent, principal_did=P,
                         action=build_action(category="purchase", human_summary="buy",
                                             granted_by_receipt_id=approval["receipt_id"]))

# 4. anyone verifies the action was human-approved with quorum
res = verify_oversight(executed, approval, required_m=2, trusted_reviewers={r1.did, r2.did, r3.did})
assert res.ok
```

> **The quorum gotcha:** building the approval does **not** cast a vote. Quorum counts
> only distinct trusted DIDs in `evidence.witness_signatures` — the builder's receipt
> signature is a different field the quorum never reads. That's why `r1` appears in
> `add_witness` above even though `r1` built the gesture. Forgetting this yields a
> confusing `quorum` failure at M-1 votes.

The runnable version with real output is
[`examples/propose_approve_verify.py`](./examples/propose_approve_verify.py)
(executed 2026-07-13):

```text
quorum 2-of-3      : True | distinct trusted signers: 2
verify_oversight   : True | stage: accepted
```

## Wire shape (what a gesture actually carries)

An oversight gesture is an ordinary ARP receipt with two extras (real serialized
output from the example above):

```jsonc
// action.machine_payload.oversight — the envelope
{"decision": "approved",
 "reviewers": ["did:key:z6Mkon3…"],          // informational; quorum does NOT read this
 "reviews_receipt_id": "aa1ec8e4-…"}

// evidence.witness_signatures[i] — one quorum vote (Ed25519 over the JCS-canonical
// receipt with `signature` + `witness_signatures` removed, so votes never invalidate
// each other or the issuer signature)
{"signer_did": "did:key:z6Mkon3…", "signature": "LUuo8tN2…"}
```

## Specification

- [`SPEC.md`](./SPEC.md) — normative gesture + quorum + gate (working draft).
- [`WHITEPAPER.md`](./WHITEPAPER.md) — design rationale.

## Related packages

| Package | Role |
| --- | --- |
| [`sm-arp`](https://github.com/Sharathvc23/sm-arp) | Agency Receipts + authority chain sm-oversight composes |
| [`sm-dat`](https://github.com/Sharathvc23/sm-dat) | standing, scoped delegation — the *asynchronous* counterpart to this package's per-action approval |
| [`sm-dissociation-receipt`](https://github.com/Sharathvc23/sm-dissociation-receipt) | downstream consumer: its `[oversight]` extra pins this package (git SHA) and wraps it as `make_oversight_gate` — an M-of-N gate before memory dissociation |
| [`sm-dissociation-guard`](https://github.com/Sharathvc23/sm-dissociation-guard) | the runtime layer where that gate is enforced at quarantine time |
| [`sm-parc`](https://pypi.org/project/sm-parc/) | sibling primitive — portable reputation credential |

## License

[MIT](./LICENSE)

---

*First release: 2026-06-07 (private phase — not on PyPI yet; install from a local
checkout or a full-SHA git pin).*

Addresses EU AI Act Art. 14 human-oversight as an open, signed, auditable protocol
artifact over ARP.
