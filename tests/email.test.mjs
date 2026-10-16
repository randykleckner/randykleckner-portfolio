import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.mjs';
function message(overrides = {}) {
  return { to: 'randy@randykleckner.com', from: 'sender@example.com', rawSize: 4,
    raw: new Response('test').body, setReject(reason) { this.rejected = reason; }, ...overrides };
}
test('stores raw email and envelope metadata only in the bound bucket', async () => {
  let saved;
  await worker.email(message(), { 'job-mail-inbound': { put: async (...args) => { saved = args; } } });
  assert.match(saved[0], /^inbox\/[a-f0-9]{64}\.eml$/);
  assert.equal(new TextDecoder().decode(saved[1]), 'test');
  assert.equal(saved[2].customMetadata.envelopeTo, 'randy@randykleckner.com');
});
test('rejects unrelated recipients before reading or storing', async () => {
  const m = message({ to: 'other@randykleckner.com', raw: null });
  await worker.email(m, {}); assert.equal(m.rejected, 'Unknown recipient');
});
test('rejects oversized declared messages', async () => {
  const m = message({ rawSize: 26 * 1024 * 1024, raw: null });
  await worker.email(m, {}); assert.match(m.rejected, /limit/);
});
test('rejects an oversized stream even when the declaration is small', async () => {
  const m = message({ raw: new Response(new Uint8Array(26 * 1024 * 1024)).body });
  await worker.email(m, {}); assert.match(m.rejected, /limit/);
});
test('storage failures propagate rather than silently losing mail', async () => {
  await assert.rejects(worker.email(message(), { 'job-mail-inbound': { put: async () => { throw new Error('storage unavailable'); } } }), /storage unavailable/);
});
test('retried content has the same storage key', async () => {
  const keys = []; const env = { 'job-mail-inbound': { put: async (key) => keys.push(key) } };
  await worker.email(message(), env); await worker.email(message(), env);
  assert.equal(keys[0], keys[1]);
});
test('HTTP requests cannot read the mailbox binding', async () => {
  const req = new Request('https://example.com/inbox/test.eml');
  const result = await worker.fetch(req, { ASSETS: { fetch: async r => { assert.equal(r, req); return new Response('Not found', { status: 404 }); } }, 'job-mail-inbound': { get: () => { throw new Error('mail access'); } } });
  assert.equal(result.status, 404);
});
