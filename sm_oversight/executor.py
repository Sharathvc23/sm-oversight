"""Single-authority local reservation store. Share one database across workers."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime

from sm_arp import chain_link

from .exact import Policy, Receipt, preflight
from .verify import OversightResult


class Executor:
    def __init__(self, path: str, policy: Policy):
        self.path = path
        self.policy = policy
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS uses (proposal TEXT PRIMARY KEY, "
                "decision TEXT NOT NULL, state TEXT NOT NULL, result TEXT, reserved_at TEXT)"
            )

    def reserve(
        self, proposal: Receipt, decision: Receipt, votes: list[dict[str, str]], outgoing: Receipt
    ) -> OversightResult:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = datetime.now(UTC)
            check = preflight(proposal, decision, votes, self.policy, outgoing, at=now)
            if not check.ok:
                return check
            key = chain_link(proposal)
            existing = db.execute("SELECT state FROM uses WHERE proposal=?", (key,)).fetchone()
            if existing:
                return OversightResult(False, existing[0], "proposal already recorded")
            db.execute(
                "INSERT INTO uses VALUES (?,?,?,NULL,?)",
                (key, chain_link(decision), "reserved", now.isoformat()),
            )
            return OversightResult(True, "reserved", key)

    def withdraw(self, proposal_digest: str) -> bool:
        """Privileged local owner operation. Remote callers require host authentication."""
        with closing(sqlite3.connect(self.path)) as db, db:
            cur = db.execute(
                "INSERT OR IGNORE INTO uses VALUES (?,'','withdrawn',NULL,NULL)", (proposal_digest,)
            )
            return cur.rowcount == 1

    def transition(self, key: str, source: str, target: str, result: str | None = None) -> bool:
        allowed = {
            "reserved": {"submitted"},
            "submitted": {"succeeded", "failed", "unknown"},
            "unknown": {"succeeded", "failed"},
        }
        if target not in allowed.get(source, set()):
            raise ValueError("invalid execution transition")
        with closing(sqlite3.connect(self.path)) as db, db:
            return (
                db.execute(
                    "UPDATE uses SET state=?,result=? WHERE proposal=? AND state=?",
                    (target, result, key, source),
                ).rowcount
                == 1
            )

    def lookup(self, key: str) -> tuple[str, str | None] | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT state,result FROM uses WHERE proposal=?", (key,)).fetchone()
            return (row[0], row[1]) if row else None

    def reservation_time(self, key: str) -> datetime | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT reserved_at FROM uses WHERE proposal=?", (key,)).fetchone()
            return datetime.fromisoformat(row[0]) if row and row[0] else None
