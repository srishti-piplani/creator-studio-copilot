import assert from 'node:assert/strict';
import { test } from 'node:test';
import { safeUrl, setupEquipment, validSetup } from '../lib/storage.ts';
import { ApiError, getSession, sendChat } from '../lib/api.ts';

const SOFTWARE_CONTEXT = ['Logic Pro (documentation reference 12.3; installed version unknown)', 'DaVinci Resolve (documentation reference 21.1; installed version unknown)'];
test('setup preserves supported hardware and excludes invented products', () => {
  assert.deepEqual(validSetup({ microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' }), { microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' });
  assert.deepEqual(validSetup({ microphone: 'Other mic', audioInterface: 'Other interface' }), { microphone: null, audioInterface: null });
});
test('equipment includes the supported hardware generation', () => {
  assert.deepEqual(setupEquipment({ microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' }, 'Help with recording'), [...SOFTWARE_CONTEXT, 'Audio-Technica AT2035', 'Focusrite Scarlett 2i2 — 2nd Gen']);
});
test('explicit question overrides saved equipment in its category', () => {
  assert.deepEqual(setupEquipment({ microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' }, 'My AT2020 is silent'), [...SOFTWARE_CONTEXT, 'Focusrite Scarlett 2i2 — 2nd Gen']);
  assert.deepEqual(setupEquipment({ microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' }, 'My Scarlett Solo is silent'), [...SOFTWARE_CONTEXT, 'Audio-Technica AT2035']);
});
test('citations reject script links and credential-bearing URLs', () => {
  assert.equal(safeUrl('javascript:alert(1)'), undefined);
  assert.equal(safeUrl('https://secret@example.com'), undefined);
  assert.equal(safeUrl('https://support.apple.com/test'), 'https://support.apple.com/test');
});
const response = { answer: 'Synthetic test answer.', intent: 'learn', session_id: 'test-session', citations: [], resource_cards: [], diagnostic_question: null, troubleshooting_status: 'idle', limitations: [] };
test('typed client sends only actual request fields and preserves session', async () => {
  const original = globalThis.fetch;
  let body: Record<string, unknown> = {};
  globalThis.fetch = async (_input, init) => { body = JSON.parse(String(init?.body)); return new Response(JSON.stringify(response)); };
  try {
    const result = await sendChat('Explain EQ', 'test-session', ['Audio-Technica AT2035']);
    assert.deepEqual(body, { message: 'Explain EQ', session_id: 'test-session', equipment: ['Audio-Technica AT2035'] });
    assert.equal(result.answer, response.answer);
  } finally { globalThis.fetch = original; }
});
test('unavailable backend produces a recoverable error', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  try { await assert.rejects(sendChat('Hello', null, []), /Check that FastAPI is running/); }
  finally { globalThis.fetch = original; }
});
test('expired session is distinct from provider failure', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('{}', { status: 404 });
  try { await assert.rejects(getSession('expired'), (error: unknown) => error instanceof ApiError && error.status === 404); }
  finally { globalThis.fetch = original; }
});
test('malformed chat response is rejected', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ answer: 'Missing metadata' }));
  try { await assert.rejects(sendChat('Hello', null, []), /unexpected response/); }
  finally { globalThis.fetch = original; }
});

test('new-user defaults differ from intentionally cleared saved setup', async () => {
  const { DEFAULT_SETUP, EMPTY_SETUP } = await import('../lib/storage.ts');
  assert.deepEqual(DEFAULT_SETUP, { microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' });
  assert.deepEqual(validSetup(EMPTY_SETUP), { microphone: null, audioInterface: null });
});
test('notebook topic inheritance retains substantive questions and recognizes a new topic', async () => {
  const { topicTitle } = await import('../lib/storage.ts');
  const prior = [{ id: '1', role: 'user' as const, text: 'What does compression do?', createdAt: '2026-10-24' }];
  assert.equal(topicTitle('Can you explain it more simply?', prior), 'What does compression do?');
  assert.equal(topicTitle('How do I export a video?', prior), 'How do I export a video?');
  assert.equal(topicTitle('What about color grading?', prior, 'Learn color grading', true), 'Learn color grading');
});
test('history retention bounds records, messages, and serialized storage', async () => {
  const { boundHistory, HISTORY_CHAR_LIMIT } = await import('../lib/storage.ts');
  const records = Array.from({ length: 30 }, (_, i) => ({ id: String(i), title: 'A topic', createdAt: '2026-10-24', updatedAt: String(i).padStart(2, '0'), sessionId: null, steps: [], draft: '', messages: Array.from({ length: 100 }, (_, n) => ({ id: `${i}-${n}`, role: 'user' as const, text: 'x'.repeat(1000), createdAt: '2026-10-24' })) }));
  const bounded = boundHistory(records);
  assert.ok(bounded.length <= 20);
  assert.ok(bounded.every(r => r.messages.length <= 80));
  assert.ok(JSON.stringify(bounded).length <= HISTORY_CHAR_LIMIT);
  assert.equal(bounded[0].id, '29');
});

test('conversation title ignores greetings and remains the first substantive topic', async () => {
  const { conversationTitle } = await import('../lib/storage.ts');
  assert.equal(conversationTitle([
    { id: '1', role: 'user', text: 'Hi', createdAt: '' },
    { id: '2', role: 'user', text: 'What does EQ do?', createdAt: '' },
    { id: '3', role: 'user', text: 'How do I export video?', createdAt: '' },
  ]), 'What does EQ do?');
});

test('configured software and matching interface generation survive POST context', async () => {
  const original = globalThis.fetch;
  let body: Record<string, unknown> = {};
  globalThis.fetch = async (_url, init) => { body = JSON.parse(String(init?.body)); return new Response(JSON.stringify(response)); };
  try {
    await sendChat('My Scarlett 2i2 has double monitoring', null, setupEquipment({ microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' }, 'My Scarlett 2i2 has double monitoring'));
    assert.deepEqual(body.equipment, [...SOFTWARE_CONTEXT, 'Audio-Technica AT2035', 'Focusrite Scarlett 2i2 — 2nd Gen']);
  } finally { globalThis.fetch = original; }
});
test('clarification replies never replace the Notebook topic, even if routing calls them new', async () => {
  const { topicTitle } = await import('../lib/storage.ts');
  const messages = [{ id: '1', role: 'user' as const, text: 'Why do I hear my voice twice while recording?', createdAt: '' }];
  for (const text of ['Logic Pro', 'USB', 'Logic Pro, USB.', 'Yes', 'No', "That didn't work"]) {
    assert.equal(topicTitle(text, messages, 'Logic Pro, USB', true), messages[0].text);
    messages.push({ id: String(messages.length + 1), role: 'user', text, createdAt: '' });
  }
  assert.equal(topicTitle('How do I export video?', messages), 'How do I export video?');
});
test('tutorial viewing hides reuse warnings, including older saved cards', async () => {
  const { resourceLicenseLabel } = await import('../lib/resources.ts');
  const tutorial = { title: 'Vocal mixing tutorial', url: 'https://example.com/tutorial', source: 'example.com', description: '', license: 'License not verified.' };
  assert.equal(resourceLicenseLabel(tutorial, 'Find vocal mixing tutorials'), null);
  assert.equal(resourceLicenseLabel({ ...tutorial, usage: 'view' }, 'Show me more'), null);
});
test('reusable samples require verified licensing provenance or retain a warning', async () => {
  const { resourceLicenseLabel } = await import('../lib/resources.ts');
  const sample = { title: 'Tabla loops', url: 'https://example.com/loops', source: 'example.com', description: '', license: 'Commercial use allowed' };
  assert.equal(resourceLicenseLabel(sample, 'Find tabla loops'), 'Check usage terms');
  assert.equal(resourceLicenseLabel({ ...sample, license_verified: true, license_source_url: 'https://example.com/license' }, 'Find tabla loops'), 'Verified for stated use · Commercial use allowed');
});

test('restricted sample terms stay visible and free download does not imply permission', async () => {
  const { resourceLicenseLabel } = await import('../lib/resources.ts');
  const resource = { title: 'Free sample pack', source: 'example.com', url: 'https://example.com/pack', description: 'Free download', usage: 'reuse' as const };
  assert.equal(resourceLicenseLabel(resource, 'Find samples'), 'Check usage terms');
  assert.match(resourceLicenseLabel({ ...resource, license_verified: true, license: 'CC BY-NC 4.0', license_source_url: 'https://example.com/pack' }, 'Find samples')!, /^Restrictions apply/);
});
