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
  `signer_did`s in `evidence.witness_signatures` — never the gesture issuer's
  receipt signature, never the informational `reviewers` list. Any change to
  what counts as a vote is a spec change (RFC-style PR to `SPEC.md` first).
- **Witness signatures never invalidate each other.** Witnesses sign the
  JCS-canonical receipt with `signature` and `witness_signatures` removed
  (`_quorum_bytes`) — adding a vote must never break earlier votes or the
  issuer signature. Test-pinned; keep it that way.
- **The gate rejects in spec order.** `not_approved → reviews_mismatch →
  quorum → authority` — each stage has a hostile-path test; a new stage lands
  with its spec section and its adversarial test in the same PR.
- **Receipts and the authority chain are ARP's.** This package owns the
  gesture, the quorum, and the gate — it never re-implements crypto,
  receipts, or chain verification (compose, don't fork `sm-arp`).
