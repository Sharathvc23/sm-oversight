# sm-oversight

**Human oversight protocol — signed approve/deny/escalate gestures with M-of-N quorum, as an auditable ARP receipt chain**

EU AI Act Article 14 requires human oversight of high-risk AI, but there is no open
protocol that turns a human's approve/deny/escalate into a **signed, verifiable
override record**. sm-oversight does. A reviewer's gesture is an ARP receipt; an
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

## Specification

- [`SPEC.md`](./SPEC.md) — normative gesture + quorum + gate (working draft).
- [`WHITEPAPER.md`](./WHITEPAPER.md) — design rationale.

## Related packages

| Package | Role |
| --- | --- |
| [`sm-arp`](https://github.com/Sharathvc23/sm-arp) | Agency Receipts + authority chain sm-oversight composes |
| [`sm-rep`](https://github.com/Sharathvc23/sm-rep) | sibling primitive — portable reputation credential |

## License

[MIT](./LICENSE)

---

*First published: 2026-06-07 | Last modified: 2026-06-07*

Addresses EU AI Act Art. 14 human-oversight as an open, signed, auditable protocol
artifact over ARP.
