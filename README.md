# sm-oversight 0.2

Verify an owner's or review panel's approval for an exact agent request before the executor makes an external change. The executor supplies its own policy, clock and outgoing arguments. The example books a simulated flight with separate owner, agent and airline keys.

Install from a pinned Git commit or run `pip install -e '.[dev]'` in a checkout, then `python examples/propose_approve_verify.py`. The example rejects a changed price and a duplicate booking and verifies the signed executor outcome.

## Integration

1. Configure `sm_oversight.exact.Policy` at the resource server. Bind the principal, agent, executor, versioned operation, enrolled reviewer keys, threshold and policy revision. Enroll one key per eligible person. Keep the owner credential outside the agent process in a deployment.
2. Use `propose` for a pending ARP receipt. Render the material request fields directly from its signed payload. Approve, deny, escalate or request changes with `decide`. Reviewers cast explicit detached votes with `vote`.
3. Reconstruct the complete request at the final adapter. Use `Executor.reserve` with that request immediately before dispatch. All workers for one executor use the same durable database. Keep a separate database per trust domain and coordinate failover to prevent split-brain execution.
4. Persist the submitted transition before calling a provider. Send the reservation key as its idempotency key. Reconcile an ambiguous response and record succeeded, failed or unknown. Use `record_outcome` for the signed observation and `inspect_outcome` for audit with trusted evidence of reservation time.
5. Authenticate owner withdrawals in the host before calling the local store. Withdrawal can win before reservation. An operation already submitted requires provider-specific cancellation.

NANDA Connect can provision an agent listing. Private assistants can use oversight directly. A deployment requiring standing delegation must validate that separately at the final adapter. Request arguments, reviewer activity and provider confirmations belong in access-controlled storage.

## Migration

0.1 stored mutable witnesses inside the signed receipt and accepted category-level authority. Its issuer signature could be reused as a vote, the gate skipped execution-signature authentication, zero was accepted as a threshold, and repeated use was possible. Version 0.2's legacy `verify_oversight` entry point denies execution. Existing downstream callers must migrate to exact approvals and reservation before enabling privileged writes. `sm_oversight.verify.inspect_legacy` inspects old records for historical category evidence. Never use its result as permission. Obtain fresh signatures for outstanding jobs. See [SPEC.md](SPEC.md) and the [release scope](docs/oversight-v02-release-scope.md).

### Separate owner terminal

Run `python -m sm_oversight.owner proposal.json trusted-policy.json owner.pem --output approval.json` on the owner's device. Use an encrypted Ed25519 PKCS#8 PEM and install the expected policy separately from the requesting agent. The command displays the signed material arguments, checks the enrolled signer and requests an interactive decision. Pass only the resulting evidence to the executor. The local demo uses ephemeral identities; the terminal command supports a separately held persistent key.

Run `node conformance/verify-booking.mjs` for the independent Node booking vector. At HTTP boundaries bound the request body before reading and use `sm_oversight.wire.parse_bundle` to reject duplicate fields, unsafe numbers and excessive nesting. Supply a trusted schema and adapter for your operation. Keep evidence bundles private; the signed request contains the material arguments in cleartext.

### Evidence profiles

| Deployment | Evidence to retain or link locally |
| --- | --- |
| Singapore agentic checkpoints | Operation boundary, policy revision, displayed request and intervention outcome |
| US risk management | Enrolled responsibility, threshold, intervention and reconciliation result |
| EU high-risk AI oversight | Information displayed, available intervention, signed decision and downstream effect |
| Brazilian automated-decision recourse | Private review request and disposition linked to the original case |

These deployment mappings identify evidence a system can collect. Applicability, retention, appeals and legal assessment belong to the deployment.

Panel reviewers can append a detached vote using the same command with --cosign approval.json and a fresh --output filename. Owner decisions include deny, escalate and request_changes. Executor construction requires its enrolled Identity. Call dispatch with the operation, request and provider adapter; the adapter receives the checked bytes. Pre-upgrade reserved rows require reconciliation and fresh approval.
