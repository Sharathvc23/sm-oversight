# Human Oversight Protocol (sm-oversight) — Working Draft

**Version (wire):** `sm-oversight/0.1`
**Status:** Working Draft. Reviewable, not yet frozen.
**Last updated:** 2026-06-07

> **Source of truth.** When a runtime disagrees with this specification, the runtime
> is wrong by definition. Conformance is verified mechanically by the test suite.

> **Conformance language.** RFC 2119 keywords (**MUST**, **SHOULD**, **MAY**).

---

## 1. Scope and non-goals

### 1.1 Scope
The oversight **gesture** (approve / deny / escalate) as an ARP receipt, the **M-of-N
quorum** over a gesture, and the **gate** that confirms an executed action was
human-approved.

### 1.2 Non-goals
The receipt format + authority chain (ARP), the reviewer UI, and escalation routing
are out of scope. sm-oversight composes ARP and records/verifies the gesture.

## 2. Relationship to other specifications
- **ARP** — gestures are ARP receipts; an approval is an `authority_granted` receipt
  and the executed action's `granted_by_receipt_id` references it, so
  `verify_authority_chain` enforces approval.
- **EU AI Act Art. 14** — the protocol produces the signed, auditable human-oversight
  record the regulation calls for.

## 3. Gestures
A gesture is a signed ARP receipt issued by a human reviewer, carrying
`action.machine_payload.oversight = {decision, reviews_receipt_id, reviewers}`.

- **approve** — category `authority_granted`. `machine_payload.granted_scope` MUST be
  `[reviewed action category]`, `granted_to_did` MUST be the agent, with a
  `grant_expires_at`. `oversight.decision` = `"approved"`.
- **deny / escalate** — category `decision_made`, `oversight.decision` =
  `"denied"` / `"escalated"`.

`reviews_receipt_id` MUST reference the proposed action receipt under review.

## 4. M-of-N quorum
A panel co-signs the gesture as `evidence.witness_signatures`, a list of
`{signer_did, signature}`. Each signature is Ed25519 over the gesture's RFC 8785
(JCS) canonical bytes EXCLUDING the receipt `signature` and the
`evidence.witness_signatures` list (so adding a witness does not change what earlier
witnesses signed). `verify_quorum(gesture, m, trusted)` MUST count only DISTINCT
`signer_did`s that are in `trusted` and whose signature verifies, and pass iff the
count ≥ `m`.

## 5. The gate
`verify_oversight(action, approval, required_m, trusted_reviewers)` MUST, in order
(reject at first failure with the named stage):

1. **not_approved** — `approval.oversight.decision` MUST be `"approved"` and it MUST
   carry a `reviews_receipt_id`.
2. **reviews_mismatch** — `action.granted_by_receipt_id` MUST equal `approval.receipt_id`.
3. **quorum** — `verify_quorum(approval, required_m, trusted_reviewers)` MUST pass.
4. **authority** — `verify_authority_chain(action, {approval.id: approval})` MUST pass
   (scope covers the action category, not expired, grantee = the agent, principal
   matches).

## 6. Conformance
A conformant implementation passes the suite under `tests/`. Every guarantee has a
happy-path test and every rejection stage a hostile-path test.

## 7. Versioning
SemVer. The gesture shape, quorum rule, and gate ordering are frozen within a major.

## 8. References
- ARP (sm-arp) — receipts + authority chain. RFC 8785 — JCS.
- EU AI Act, Article 14 (human oversight).
