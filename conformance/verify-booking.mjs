// Independent Node verifier for the committed booking fixture (safe integer JSON profile).
import {createHash, createPublicKey, verify} from 'node:crypto';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';

const b = JSON.parse(readFileSync(new URL('./booking.json', import.meta.url)));
function canonical(v) {
  if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']';
  if (v && typeof v === 'object') return '{' + Object.keys(v).sort().map(
    k => JSON.stringify(k) + ':' + canonical(v[k])).join(',') + '}';
  return JSON.stringify(v);
}
const digest = value => createHash('sha256').update(canonical(value)).digest('hex');
function key(did) {
  assert.ok(did.startsWith('did:key:z'));
  const alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  let n = 0n;
  for (const ch of did.slice(9)) {
    const i = alphabet.indexOf(ch); assert.ok(i >= 0); n = 58n*n + BigInt(i);
  }
  const bytes = Buffer.from(n.toString(16).padStart(68,'0'), 'hex');
  assert.equal(bytes.length,34); assert.equal(bytes.readUInt16BE(),0xed01);
  return createPublicKey({key:Buffer.concat([Buffer.from('302a300506032b6570032100','hex'),
    bytes.subarray(2)]),format:'der',type:'spki'});
}
function check(bundle, policy, outgoing, at) {
  const {proposal:p, decision:d, votes} = bundle;
  for (const receipt of [p,d]) {
    const {signature,...body} = receipt;
    assert.ok(verify(null,Buffer.from(canonical(body)),key(body.issuer_did),Buffer.from(signature,'base64')));
    assert.equal(body.principal_did,policy.principal);
  }
  assert.equal(p.issuer_did,policy.agent); assert.ok(policy.reviewers.includes(d.issuer_did));
  const intent=p.action.machine_payload, choice=d.action.machine_payload;
  assert.equal(p.action.outcome,'pending'); assert.equal(d.action.category,'decision_made'); assert.equal(d.action.outcome,'completed');
  assert.equal(intent.version,'sm-oversight/0.2'); assert.equal(choice.version,intent.version);
  assert.equal(choice.policy,digest(policy)); assert.equal(intent.policy,choice.policy);
  assert.deepEqual(intent.request,outgoing); assert.equal(choice.decision,'approve');
  assert.equal(choice.proposal,'sha256:'+digest(p));
  assert.ok(Date.parse(p.issued_at)<=Date.parse(d.issued_at) && Date.parse(d.issued_at)<=Date.parse(at)
    && Date.parse(at)<Date.parse(choice.expires));
  const seen=new Set();
  for (const {signer,signature} of votes) {
    assert.ok(policy.reviewers.includes(signer) && !seen.has(signer)); seen.add(signer);
    const msg=Buffer.concat([Buffer.from('sm-oversight/0.2/vote\0'),Buffer.from(canonical({
      decision_digest:'sha256:'+digest(d),signer}))]);
    assert.ok(verify(null,msg,key(signer),Buffer.from(signature,'base64')));
  }
  assert.ok(policy.threshold>0 && seen.size>=policy.threshold);
}
check(b,b.policy,b.request,b.at);
assert.throws(()=>check(b,b.policy,{...b.request,fare_minor:44700},b.at));
assert.throws(()=>check({...b,votes:[{...b.votes[0],signature:b.decision.signature}]},b.policy,b.request,b.at));
console.log('Booking fixture verified. Fare substitution and copied vote rejected.');
