# Vendored dependencies

## `sm_arp/`

Vendored from **github.com/Sharathvc23/sm-arp at tag `v0.1.3`**
(commit `ef746c41d037a39649e3991663b9d1070d07b620`) — the canonical Agency
Receipt Protocol library (receipt build / sign / verify / store, `did:key`
identity, JCS canonical bytes, per-issuer hash chain). `sm-oversight` records
its approve/deny/escalate gestures as an ARP receipt chain, so it builds on
`sm_arp`'s issue/verify primitives.

### Why it's vendored
A `sm-arp` PyPI/git dependency adds an external fetch to every `sm-oversight`
build, and at the time of vendoring `sm-arp` is not published to PyPI. Both
sibling runtimes (`sm-member-sdk`, `sm-chapter`) already vendor `sm_arp/`
in-tree; `sm-oversight` matches that proven, self-contained pattern. The
library is small and pinned, so vendoring removes the external fetch entirely.

### Scope
Only the package modules `sm-oversight` uses are vendored — `__init__.py`,
`identity.py`, `receipts.py`, `store.py` — **not** sm-arp's own test suite, and
not `vrp.py` (the VRP/reputation core, which `sm-oversight` does not import).
The one third-party runtime dependency, `jcs` (RFC 8785), is declared directly
in `pyproject.toml`.

### It is upstream's code, kept pristine
`sm_arp/` is excluded from this repo's ruff and strict-mypy gates (see
`pyproject.toml`). Don't edit it here — fix it upstream in sm-arp and re-sync.

### Re-syncing to a new sm-arp release
```bash
git -C <path-to-sm-arp> archive vX.Y.Z \
    sm_arp/__init__.py sm_arp/identity.py sm_arp/receipts.py sm_arp/store.py \
  | tar -x -C <path-to-sm-oversight>/
```
Then bump the pinned version + commit above and re-run the suite. If `sm-arp`
is published to PyPI, this can revert to a normal pinned PyPI dependency.
