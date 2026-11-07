from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sm_arp import Identity, chain_link, verify_receipt

from sm_oversight import verify_oversight
from sm_oversight.exact import (
    Policy,
    decide,
    inspect_outcome,
    preflight,
    propose,
    record_outcome,
    vote,
)
from sm_oversight.executor import Executor


@pytest.fixture
def bundle():
    owner, agent, executor, second = (Identity.generate() for _ in range(4))
    policy = Policy(owner.did, agent.did, executor.did, "book/1", (owner.did, second.did), 2, "r1")
    req = {"fare": 43200, "currency": "USD", "payee": "airline:a"}
    proposal = propose(agent, policy, req, summary="Book")
    decision = decide(
        owner,
        proposal,
        policy,
        decision="approve",
        expires=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    votes = [vote(key, decision) for key in (owner, second)]
    return owner, executor, policy, req, proposal, decision, votes


def test_exact_and_hostile(bundle):
    owner, executor, pol, req, p, d, votes = bundle
    now = datetime.now(UTC)

    def check(prop=p, decision=d, signatures=votes, policy=pol, outgoing=req, at=now):
        return preflight(prop, decision, signatures, policy, outgoing, at=at).ok

    assert check() and verify_receipt(d).ok
    assert not check(outgoing={**req, "payee": "airline:b"})
    assert not check(prop={**p, "signature": "AA=="})
    assert not check(decision={**d, "signature": "AA=="})
    assert not check(signatures=[{"signer": owner.did, "signature": d["signature"]}, votes[1]])
    assert not check(signatures=votes[:1])
    assert not check(signatures=[votes[0], votes[0]])
    assert not check(policy=replace(pol, executor=owner.did))
    assert not check(at=now + timedelta(hours=1))
    assert not check(prop={})
    assert not check(decision=decide(owner, p, pol, decision="deny", expires=now.isoformat()))
    assert not verify_oversight(p, d, required_m=0, trusted_reviewers=set()).ok
    for threshold in (0, -1, True, 3):
        with pytest.raises(ValueError):
            replace(pol, threshold=threshold)
    receipt = record_outcome(executor, pol, p, d, req, state="unknown", provider_ref="")
    assert inspect_outcome(receipt, p, d, votes, pol, req, reserved_at=now).stage == "unknown"
    assert not inspect_outcome(
        {**receipt, "signature": "AA=="}, p, d, votes, pol, req, reserved_at=now
    ).ok


def test_reservation_races_and_restart(tmp_path, bundle):
    _, _, policy, req, p, d, votes = bundle
    path = str(tmp_path / "db")
    runtime = Executor(path, policy)

    def reserve(_):
        return runtime.reserve(p, d, votes, req).ok

    with ThreadPoolExecutor(4) as workers:
        assert sum(workers.map(reserve, range(8))) == 1
    key = chain_link(p)
    assert not runtime.withdraw(key)
    assert runtime.transition(key, "reserved", "submitted")
    recovered = Executor(path, policy)
    assert recovered.lookup(key) == ("submitted", None)
    assert not recovered.reserve(p, d, votes, req).ok
    assert recovered.transition(key, "submitted", "unknown")
    assert recovered.transition(key, "unknown", "succeeded", "confirmation")
    assert recovered.lookup(key) == ("succeeded", "confirmation")
    with pytest.raises(ValueError):
        recovered.transition(key, "succeeded", "reserved")
    fresh = Executor(str(tmp_path / "other"), policy)
    assert fresh.withdraw(key)
    assert fresh.reserve(p, d, votes, req).stage == "withdrawn"


def test_wire_limits():
    from sm_oversight.wire import parse_bundle

    assert parse_bundle(b'{"price":[43200]}') == {"price": [43200]}
    for bad in (
        b'{"a":1,"a":2}',
        b"[]",
        b'{"a":1.2}',
        b"x" * 262145,
        b'{"a":' + b"[" * 40 + b"0" + b"]" * 40 + b"}",
    ):
        with pytest.raises(ValueError):
            parse_bundle(bad)


def test_separate_owner_review(bundle):
    from sm_oversight.owner import review

    _, _, policy, _, proposal, _, _ = bundle
    assert '"fare": 43200' in review(proposal, policy)
    with pytest.raises(ValueError):
        review(proposal, replace(policy, revision="other"))
    with pytest.raises(ValueError):
        review({**proposal, "signature": "AA=="}, policy)
