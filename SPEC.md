# Human oversight protocol 0.2

The local policy digest is lowercase SHA-256 over the JCS representation of Policy fields with sorted reviewer DIDs. The signed pending proposal carries the wire version, policy digest and complete JSON request. A completed decision receipt binds the proposal's ARP chain_link, policy digest, decision and expiry. Both receipts bind the principal. The proposal issuer must be the configured agent and the decision issuer an eligible reviewer.

A vote is standard base64 Ed25519 over the ASCII purpose sm-oversight/0.2/vote, a single zero byte, and the JCS object with decision_digest (the full signed decision chain_link) and signer (the reviewer's DID). Votes travel outside both receipts. The verifier requires distinct enrolled keys, a positive threshold, and proposal issuance <= decision issuance <= trusted time < expiry. Only approve admits preflight. The final request must reproduce the committed arguments. Each operation version defines its own material fields and units.

The SQLite reference executor serializes withdrawal and reservation, using the signed proposal digest as its unique key. Approval by another panel member for the same proposal cannot spend it again. Preflight is stateless. A successful reservation supplies the provider idempotency key. A signed executor outcome binds the request digest and both receipt links. Historical verification requires an independently trusted reservation time and policy snapshot.

## Legacy 0.1 wire reference

The following historical specification documents the old format. Its acceptance stages apply only to archived records and are implemented by `sm_oversight.verify.inspect_legacy`. The 0.1 entry point `verify_oversight` is deprecated and denies new execution unconditionally (§5). Since 0.3 the witness entry key is `witness_did` (ARP §5) and the bytes a witness signs are the issuer-signed bytes as computed by `sm_arp.canonical_bytes(gesture, include_signature=False)` — one rule shared with the issuer signature, the chain link and VRP corroboration (sm-arp ≥ 0.4), so appending a witness never invalidates the issuer signature.

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

`grant_expires_at` MUST be an RFC 3339 timestamp carrying a UTC offset;
`build_oversight_approval` rejects anything else (`ValueError`) because
`sm_arp.verify_authority_chain` fails a grant whose expiry does not parse.

`oversight.reviewers` is informational metadata asserted by the issuer — who was
asked to review. Nothing verifies it and nobody listed in it has signed anything.
Quorum is computed over `evidence.witness_signatures` only (§4).

> **Note:** the gesture issuer's own receipt `signature` is NOT read as a quorum
> vote. A reviewer who builds the gesture MUST also `add_witness` themselves to be
> counted — quorum counts only distinct trusted witness DIDs in
> `evidence.witness_signatures`. Because witnesses sign the issuer-signed bytes
> (§4), the issuer's `add_witness` entry is byte-identical to their receipt
> signature (Ed25519 is deterministic); either way the issuer is one trusted
> reviewer counted once under their own DID, and the signature verifies under no
> other DID.

## 4. M-of-N quorum
A panel co-signs the gesture as `evidence.witness_signatures`, a list of
`{witness_did, signature}` — the ARP §5 witness entry, so an entry produced by
`sm_arp.vrp.cosign_receipt` is a quorum vote and an entry produced by `add_witness`
corroborates under `sm_arp.vrp.is_corroborated` when the witness is the receipt's
counterparty. Writers MUST emit `witness_did`. Readers MUST also accept the
pre-0.3 key `signer_did`; when both are present `witness_did` wins (the precedence
`sm_arp.vrp` applies).

Each signature is Ed25519 over `sm_arp.canonical_bytes(gesture,
include_signature=False)`: the gesture's RFC 8785 (JCS) canonical bytes EXCLUDING
the receipt `signature` and the `evidence.witness_signatures` list (an `evidence`
object emptied by that removal is dropped). These are exactly the bytes the issuer
signed, so adding a witness changes neither what earlier witnesses signed nor the
issuer signature nor `chain_link`. Implementations MUST NOT restate this rule; they
call sm-arp.

`verify_quorum(gesture, m, trusted)` MUST first require `1 ≤ m ≤ |trusted|` and
then that `sm_arp.verify_receipt(gesture)` (strict) accepts the gesture — a gesture
whose own issuer signature does not verify is rejected at stage `receipt` however
many witnesses it carries. It MUST then count only DISTINCT witness DIDs that are
in `trusted` and whose signature verifies over the bytes above, and pass iff the
count ≥ `m`.

## 5. The gate — historical inspection only
Category-level approval is not permission to execute. The permission-granting path
is the 0.2 exact-action protocol above: `sm_oversight.exact.preflight` authenticates
the exact request and `sm_oversight.executor.Executor.reserve` spends the approval
once. The 0.1 gate algorithm survives as
`sm_oversight.verify.inspect_legacy(action, approval, required_m, trusted_reviewers)`,
whose accepting result is `stage == "legacy"` and MUST be read as evidence about an
archived record, never as authorization. It MUST, in order (reject at first failure
with the named stage):

1. **receipt** — `sm_arp.verify_receipt(approval)` (strict) MUST accept the gesture:
   its own issuer signature verifies. Witnesses co-sign the issuer-signed body, so a
   gesture whose issuer signature is garbage is rejected before any witness counts.
2. **issuer** — `approval.issuer_did` MUST be in `trusted_reviewers`.
3. **signature** — the executed `action`'s own issuer signature MUST verify.
4. **not_approved** — `approval.oversight.decision` MUST be `"approved"` and it MUST
   carry a `reviews_receipt_id`.
5. **reviews_mismatch** — `action.granted_by_receipt_id` MUST equal `approval.receipt_id`.
6. **quorum** — `verify_quorum(approval, required_m, trusted_reviewers)` MUST pass
   (a `receipt` failure there is reported under its own stage).
7. **authority** — `verify_authority_chain(action, {approval.receipt_id: approval})`
   MUST pass (grant signature authenticated, scope covers the action category, not
   expired, grantee = the agent, principal matches).

`verify_oversight(action, approval, required_m, trusted_reviewers)` is the
deprecated 0.1 entry point. It implements no algorithm: it MUST emit a
`DeprecationWarning` and return `ok=False, stage="legacy_denied"` unconditionally,
so a caller still wired to it fails closed. It is kept through 0.x and removed in
1.0; migrate to the exact path.

## 6. Conformance
A conformant implementation passes the suite under `tests/`. Every guarantee has a
happy-path test and every rejection stage a hostile-path test.

## 7. Versioning
SemVer. The gesture shape, quorum rule, and gate ordering are frozen **within a major**
once one exists — under 0.x (the current Working Draft) they may still change with the
spec.

## 8. References
- ARP (sm-arp) — receipts + authority chain. RFC 8785 — JCS.
- EU AI Act, Article 14 (human oversight).
