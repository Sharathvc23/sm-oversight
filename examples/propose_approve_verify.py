"""Local personal-agent booking with separate agent, owner and executor identities."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sm_arp import Identity
from sm_oversight.exact import Policy, decide, inspect_outcome, propose, record_outcome, vote
from sm_oversight.executor import Executor

owner, agent, airline = (Identity.generate() for _ in range(3))
policy = Policy(owner.did, agent.did, airline.did, "flight.book/1", (owner.did,), 1, "1")
request = {
    "flight": "DEMO-42",
    "passenger": "local-passenger-1",
    "currency": "USD",
    "total_minor": 43200,
    "fare_terms": "economy/nonrefundable",
    "quote": "demo-quote",
}
proposal = propose(agent, policy, request, summary="Review flight booking")
# The review surface displays this structured request before requesting the owner's signature.
print("Review", proposal["action"]["machine_payload"]["request"])
expires = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
decision = decide(owner, proposal, policy, decision="approve", expires=expires)
votes = [vote(owner, decision)]
with TemporaryDirectory() as tmp:
    executor = Executor(str(Path(tmp) / "reservations.sqlite"), policy, airline)
    assert not executor.reserve(proposal, decision, votes, {**request, "total_minor": 44700}).ok
    reservation = executor.reserve(proposal, decision, votes, request)
    assert reservation.ok
    reserved_at = executor.reservation_time(reservation.detail)
    assert reserved_at is not None
    assert not executor.reserve(proposal, decision, votes, request).ok
    assert executor.dispatch(reservation.detail, policy.operation, request,
                             lambda op, body, key: print(op, body.decode(), key))
    # Simulated provider confirmation. Use reservation.detail as the provider idempotency key.
    assert executor.transition(reservation.detail, "submitted", "succeeded", "demo-confirmation")
    receipt = record_outcome(
        airline,
        policy,
        proposal,
        decision,
        request,
        state="succeeded",
        provider_ref="demo-confirmation",
    )
    result = inspect_outcome(
        receipt, proposal, decision, votes, policy, request, reserved_at=reserved_at
    )
    assert result.ok
    print("Executor outcome", result.stage)
