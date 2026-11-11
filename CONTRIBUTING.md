# Contributing to sm-oversight

Contributions are accepted under the Developer Certificate of Origin (DCO)
sign-off model. Add `Signed-off-by: Your Name <you@example.com>` to every commit
(`git commit -s`).

## Change process

1. Spec-affecting changes open a PR updating the **spec (`SPEC.md`), the tests,
   and the code together**. The `tests/` suite is the authoritative behavioural
   specification of the package.
2. The gate is ruff → mypy → pytest (`uv run pytest -q`); CI runs the same.
   Push only when green.

## House rules

- **Quorum is witnesses, only witnesses.** Votes are distinct trusted
  `witness_did`s in `evidence.witness_signatures` (`signer_did` is read as the
  pre-0.3 alias, never written) — never the informational `reviewers` list. Any
  change to what counts as a vote is a spec change (RFC-style PR to `SPEC.md`
  first).
- **One canonicalization rule, and it is sm-arp's.** Witnesses sign
  `sm_arp.canonical_bytes(gesture, include_signature=False)` — the issuer-signed
  bytes, with `signature` and `evidence.witness_signatures` detached. Never
  restate that rule here; a second copy is how witnessing came to invalidate the
  issuer signature. Adding a vote must never break earlier votes, the issuer
  signature or `chain_link`. Test-pinned; keep it that way.
- **Authenticate the gesture before counting votes.** `verify_quorum` and
  `inspect_legacy` run `sm_arp.verify_receipt` (strict) first; witnesses never
  substitute for the issuer signature.
- **Legacy inspection rejects in spec order.** `receipt → issuer → signature →
  not_approved → reviews_mismatch → quorum → authority` — each stage has a
  hostile-path test; a new stage lands with its spec section and its adversarial
  test in the same PR. `verify_oversight` denies unconditionally and stays that
  way: permission is `exact.preflight` + `Executor.reserve`.
- **Receipts and the authority chain are ARP's.** This package owns the
  gesture, the quorum, and the gate — it never re-implements crypto,
  receipts, or chain verification (compose, don't fork `sm-arp`).
