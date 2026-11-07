"""Single-authority local reservation store. Share one database across workers."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from copy import deepcopy
from datetime import UTC, datetime

import jcs
from sm_arp import Identity, chain_link

from .exact import Policy, Receipt, _digest, preflight
from .verify import OversightResult


class Executor:
    def __init__(self, path: str, policy: Policy, identity: Identity):
        if identity.did != policy.executor:
            raise ValueError("executor credential does not match policy")
        self.path = path
        self.policy = policy
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS uses (proposal TEXT PRIMARY KEY, "
                "decision TEXT NOT NULL, state TEXT NOT NULL, result TEXT, reserved_at TEXT)"
            )

            columns = {row[1] for row in db.execute("PRAGMA table_info(uses)")}
            for name in ("operation", "request_digest", "executor"):
                if name not in columns:
                    db.execute(f"ALTER TABLE uses ADD COLUMN {name} TEXT")

    def reserve(
        self, proposal: Receipt, decision: Receipt, votes: list[dict[str, str]], outgoing: Receipt
    ) -> OversightResult:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = datetime.now(UTC)
            outgoing = deepcopy(outgoing)
            check = preflight(proposal, decision, votes, self.policy, outgoing, at=now)
            if not check.ok:
                return check
            key = chain_link(proposal)
            existing = db.execute("SELECT state FROM uses WHERE proposal=?", (key,)).fetchone()
            if existing:
                return OversightResult(False, existing[0], "proposal already recorded")
            db.execute(
                "INSERT INTO uses(proposal,decision,state,reserved_at,"
                "operation,request_digest,executor)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    key,
                    chain_link(decision),
                    "reserved",
                    now.isoformat(),
                    self.policy.operation,
                    _digest(outgoing),
                    self.policy.executor,
                ),
            )
            return OversightResult(True, "reserved", key)

    def withdraw(self, proposal_digest: str) -> bool:
        """Privileged local owner operation. Remote callers require host authentication."""
        with closing(sqlite3.connect(self.path)) as db, db:
            cur = db.execute(
                "INSERT OR IGNORE INTO uses(proposal,decision,state) VALUES (?,'','withdrawn')",
                (proposal_digest,),
            )
            return cur.rowcount == 1

    def dispatch(
        self, key: str, operation: str, request: Receipt, send: Callable[[str, bytes, str], None]
    ) -> bool:
        """Pass the verified operation and immutable canonical bytes to the trusted adapter."""
        import hashlib

        body = bytes(jcs.canonicalize(request))
        with closing(sqlite3.connect(self.path)) as db, db:
            claimed = db.execute(
                "UPDATE uses SET state='submitted' WHERE proposal=? AND state='reserved' "
                "AND operation=? AND request_digest=? AND executor=?",
                (key, operation, hashlib.sha256(body).hexdigest(), self.policy.executor),
            )
            if not claimed.rowcount:
                return False
        # A timeout leaves submitted durable for reconciliation.
        send(operation, body, key)
        return True

    def transition(self, key: str, source: str, target: str, result: str | None = None) -> bool:
        allowed = {
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
