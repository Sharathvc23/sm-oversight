"""sm-oversight — Human Oversight Protocol.

Signed approve / deny / escalate gestures with M-of-N quorum, forming an auditable
ARP receipt chain (agent proposed → humans reviewed → decision recorded). The
approve gesture is an ARP authority grant, so an executed action that references it
is verifiably human-approved (EU AI Act Art. 14).

    from sm_oversight import build_oversight_approval, add_witness, verify_quorum
    from sm_oversight.exact import propose, decide, vote, preflight
    from sm_oversight.executor import Executor

Permission for a privileged write comes from the exact-action path (``exact`` +
``Executor``). ``verify_oversight`` is the deprecated 0.1 gate and always denies;
``verify.inspect_legacy`` reads 0.1 records as historical evidence only.

Composes ``sm-arp`` >= 0.4 (receipts, one detached-witness canonicalization rule,
authority chain).
"""

from __future__ import annotations

from .context import APPROVED, DENIED, ESCALATED, OVERSIGHT_KEY
from .gesture import build_oversight_approval, build_oversight_decision
from .quorum import QuorumResult, add_witness, verify_quorum
from .verify import OversightResult, verify_oversight

__version__ = "0.3.0"

__all__ = [
    "APPROVED",
    "DENIED",
    "ESCALATED",
    "OVERSIGHT_KEY",
    "OversightResult",
    "QuorumResult",
    "add_witness",
    "build_oversight_approval",
    "build_oversight_decision",
    "verify_oversight",
    "verify_quorum",
]
