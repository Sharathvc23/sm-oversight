"""sm-oversight constants — the oversight decisions and the machine_payload key."""

from __future__ import annotations

# The key under an ARP receipt's action.machine_payload that carries the oversight
# envelope: {"decision", "reviews_receipt_id", "reviewers"}.
OVERSIGHT_KEY = "oversight"

# Oversight decisions.
APPROVED = "approved"
DENIED = "denied"
ESCALATED = "escalated"

DECISIONS = frozenset({APPROVED, DENIED, ESCALATED})

__all__ = ["APPROVED", "DECISIONS", "DENIED", "ESCALATED", "OVERSIGHT_KEY"]
