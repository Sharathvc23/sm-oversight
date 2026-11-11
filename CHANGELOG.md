# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] — 2026-11-11

Audit 2026-11. Requires `sm-arp>=0.4.0`.

### Changed
- `quorum`: the bytes a witness signs are `sm_arp.canonical_bytes(gesture,
  include_signature=False)` — sm-arp's single detached-witness rule — instead of
  a private re-implementation. Witnessing no longer invalidates the issuer
  signature or `chain_link` (that is sm-arp 0.4's change; this release relies on
  it and pins it).
- `add_witness` writes `witness_did` (ARP §5), not `signer_did`. Readers accept
  both; `witness_did` wins when both are present. An `sm_arp.vrp.cosign_receipt`
  entry counts toward quorum and an `add_witness` entry corroborates under
  `sm_arp.vrp.is_corroborated`.
- `verify_quorum` and `verify.inspect_legacy` authenticate the gesture receipt
  first (`sm_arp.verify_receipt`, strict) and reject at stage `receipt` if the
  issuer signature does not verify, however many witnesses it carries.
  `inspect_legacy` also requires the gesture issuer to be a trusted reviewer
  (stage `issuer`), and reports quorum-stage failures under the quorum result's
  own stage.
- `verify_oversight` is deprecated: it still denies unconditionally, now at
  stage `legacy_denied` (was `legacy`) and with a `DeprecationWarning`. SPEC §5
  documents `inspect_legacy` as the historical-inspection algorithm and the
  exact path (`exact.preflight` + `Executor.reserve`) as the only permission.
- `build_oversight_approval` raises `ValueError` for a `grant_expires_at` that is
  not an RFC 3339 timestamp with a UTC offset. `reviewers` is documented as
  issuer-asserted metadata; quorum is over `evidence.witness_signatures` only.
- Dependency: `sm-arp>=0.4.0` (was `>=0.3.2`). CI installs sm-arp from the
  0.4.0 merge commit until 0.4.0 is on PyPI.

### Added
- `quorum.witness_bytes`, `quorum.witness_did`, `quorum.WITNESS_DID`,
  `quorum.LEGACY_WITNESS_DID`.
- Tests: co-signed gesture passes strict `verify_receipt` with unchanged issuer
  signature and chain link; garbage issuer signature + three valid witnesses is
  rejected; tampered payload rejected; untrusted issuer rejected; issuer
  signature cannot be attributed to another reviewer; legacy `signer_did`
  entries still count; VRP interop both ways; expiry validation; `reviewers` is
  not a vote; legacy gate always denies.

### Fixed
- CHANGELOG header typo (`n## 0.2.0`) and ordering.

## [0.2.0]

Add exact requests, detached votes, owner and panel policies, preflight,
durable reservation, withdrawal, outcome verification and a booking example.
Legacy execution callers must migrate and obtain fresh approvals.

## [0.1.0] — 2026-06-07

### Added
- Initial working-draft release of sm-oversight.
