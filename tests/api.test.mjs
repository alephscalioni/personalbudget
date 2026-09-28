import test from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../frontend/js/ui.js';

test('a temporary read failure recovers without user resubmission', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'setTimeout', (fn) => fn());
  t.mock.method(globalThis, 'fetch', async () => ++calls === 1
    ? new Response('Unavailable', { status: 503 })
    : Response.json({ authenticated: true }));
  assert.deepEqual(await api('session'), { authenticated: true });
  assert.equal(calls, 2);
});

test('unavailable server stops after three reads and explains the failure', async (t) => {
  t.mock.method(globalThis, 'setTimeout', (fn) => fn());
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response('Unavailable', { status: 502 }));
  await assert.rejects(api('session'), /servidor está temporariamente indisponível/);
  assert.equal(fetch.mock.callCount(), 3);
});

test('password requests are never automatically resubmitted', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response('Unavailable', { status: 503 }));
  await assert.rejects(api('password/reset', 'POST', { token: 'test' }), /temporariamente indisponível/);
  assert.equal(fetch.mock.callCount(), 1);
});
