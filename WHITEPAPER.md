# Human Oversight Protocol (sm-oversight) — Whitepaper

Addresses EU AI Act Art. 14 human oversight as an open protocol over ARP.

## Abstract
Regulators require that a human can oversee high-risk AI — approve, deny, escalate —
but oversight today is a UI gesture that leaves no portable, verifiable trace. When an
agent later acts, there is no cryptographic proof a human approved it, nor that the
required number of humans did. sm-oversight turns each oversight gesture into a signed
ARP receipt and a verifiable chain, so "a human approved this, with quorum" becomes a
checkable fact rather than a log line on someone's server.

## 1. Problem
Human-in-the-loop controls are implemented per-product and per-UI. They produce audit
logs the operator controls, not signed artifacts a third party (regulator, insurer,
downstream agent) can verify. And "human approved" is usually one click by one person —
no notion of an M-of-N panel for consequential actions.

## 2. Design axioms
1. **Oversight is authority.** Approving an action is granting authority for it; reuse
   ARP's authority chain rather than invent a parallel mechanism.
2. **Quorum is cryptographic.** M-of-N is M valid signatures from distinct trusted
   reviewers, not a database flag.
3. **Compose, don't fork.** Ride on existing ARP categories + a machine_payload
   envelope; no change to the receipt wire format.

## 3. The oversight primitive
A gesture is an ARP receipt; an approval doubles as an `authority_granted` grant scoped
to the proposed action. The executed action references the approval; the gate then
composes three checks — reference, quorum, authority — into a single "human-approved?"
verdict. Because approval reuses the authority chain, an ARP 0.2 verifier that requires
authority for high-stakes actions *already* refuses an un-approved high-stakes action.

## 4. Composition with the portfolio
```
  ARP (receipt + authority chain)
        │
        ├── sm-oversight : approve = authority_granted gesture (M-of-N witnessed)
        │                  executed action.granted_by → the approval
        └── sm-parc      : portable reputation credential (sibling primitive)
```

## 5. Open questions
- First-class `oversight_*` ARP categories (vs the machine_payload envelope).
- Standard escalation routing + reviewer-panel discovery.
- Binding the proposed↔executed receipts more tightly (beyond granted_by).
