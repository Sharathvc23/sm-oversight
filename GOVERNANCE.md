# Governance

## Scope

| In scope | Out of scope |
| --- | --- |
| the oversight gesture (approve/deny/escalate), M-of-N quorum, and the human-approval gate | the receipt format + authority chain (ARP), the reviewer UI/emitter, escalation routing |

The primitive owns one thing — turning a human oversight gesture into a signed,
quorum-verifiable, ARP-anchored record. Anything else belongs to a companion package
or the consumer.

## Versioning
Semantic Versioning 2.0.0. The gesture shape, quorum rule, and gate ordering are frozen
within a major; a change requires an RFC-style PR to `SPEC.md` before code.

## Conformance
The test suite under `tests/` is the authoritative behavioural specification. Every
guarantee has a happy-path test; every rejection stage a hostile-path test. A behaviour
change without a test change is a bug.

## Contributions
- PRs must include tests and pass `ruff` + `mypy --strict` + `pytest`.
- No expansion of the gesture/quorum/gate surface without an accepted RFC.
- Generic primitive only — no domain- or deployment-specific content.
- Sign off with the Developer Certificate of Origin (DCO).

## Attribution
Composes sm-arp (ARP + authority chain); sibling to sm-rep. Addresses EU AI Act Art. 14.
