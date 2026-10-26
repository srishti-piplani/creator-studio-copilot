import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { sendChatWithProgress } from '../lib/chat-stream.ts';

const result = { answer: 'Synthetic final answer. [K1]', intent: 'learn', session_id: 'test-session', citations: [{ id: 'K1', guide_title: 'Synthetic guide' }], resource_cards: [], diagnostic_question: null, troubleshooting_status: 'idle', limitations: [], topic_title: 'Explain gain' };
function stream(chunks: string[]) {
  return new Response(new ReadableStream({ start(controller) {
    for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
    controller.close();
  } }), { headers: { 'Content-Type': 'text/event-stream' } });
}

test('fragmented SSE orders actual progress and returns the unchanged renderable response', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => stream([': keepalive\n\nevent: pro',
    'gress\ndata: {"action":"knowledge","label":"Searching Studio Knowledge","status":"started"}\n',
    '\nevent: progress\ndata: {"action":"knowledge","label":"Searching Studio Knowledge","status":"completed"}\n\n',
    `event: final\ndata: ${JSON.stringify(result)}\n\n`]);
  const updates: string[] = [];
  try {
    const response = await sendChatWithProgress('Explain gain', null, [], { onProgress: p => updates.push(`${p.action}:${p.status}`) });
    assert.deepEqual(updates, ['knowledge:started', 'knowledge:completed']);
    assert.deepEqual(response, result); // Existing Answer rendering consumes this exact schema.
  } finally { globalThis.fetch = original; }
});

test('a dropped stream falls back to POST using the same request ID and session', async () => {
  const original = globalThis.fetch;
  const requests: { url: string; body: Record<string, unknown> }[] = [];
  globalThis.fetch = async (url, init) => {
    requests.push({ url: String(url), body: JSON.parse(String(init?.body)) });
    return requests.length === 1 ? stream(['event: progress\ndata: {"action":"understand","label":"Understanding your question","status":"started"}\n\n']) : new Response(JSON.stringify(result));
  };
  let fallback = false;
  try {
    assert.deepEqual(await sendChatWithProgress('Explain gain', 'existing-session', ['Logic Pro'], { requestId: 'fixed-id', onProgress: () => {}, onFallback: () => { fallback = true; } }), result);
    assert.ok(fallback);
    assert.equal(requests.length, 2);
    assert.ok(requests[0].url.endsWith('/chat/stream'));
    assert.ok(requests[1].url.endsWith('/chat'));
    assert.deepEqual(requests[0].body, requests[1].body);
    assert.equal(requests[1].body.session_id, 'existing-session');
  } finally { globalThis.fetch = original; }
});

test('old backends without SSE fall back gracefully without inventing progress', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => ++calls === 1 ? new Response('{}', { status: 404 }) : new Response(JSON.stringify(result));
  const progress: unknown[] = [];
  try {
    assert.deepEqual(await sendChatWithProgress('Explain gain', null, [], { onProgress: p => progress.push(p) }), result);
    assert.equal(progress.length, 0);
  } finally { globalThis.fetch = original; }
});

test('application errors are surfaced rather than silently re-running the request', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return stream(['event: error\ndata: {"status":404,"message":"Session not found"}\n\n']); };
  try {
    await assert.rejects(sendChatWithProgress('Explain gain', 'expired', [], { onProgress: () => {} }), /Session not found/);
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});

test('focused card styling preserves the existing responsive grid rules', () => {
  const css = fs.readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(css, /\.mode-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3,/);
  assert.match(css, /@media\s*\(max-width:\s*420px\)[\s\S]*?\.mode-grid\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.match(css, /\.landing-setup-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,/);
  assert.match(css, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.landing-setup-grid\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.match(css, /\.mode-card:focus-visible/);
  assert.match(css, /\.equipment-rack \.landing-setup-card[^}]*background:\s*transparent/);
});

test('repeated activities are grouped while failures and raw events survive', async () => {
  const { groupActivity } = await import('../lib/activity.ts');
  const events = [
    { action: 'documentation', label: 'Reading official documentation', status: 'started' as const },
    { action: 'documentation', label: 'Reading official documentation', status: 'failed' as const },
    { action: 'documentation', label: 'Reading official documentation', status: 'started' as const },
    { action: 'documentation', label: 'Reading official documentation', status: 'completed' as const },
  ];
  const grouped = groupActivity(events);
  assert.equal(grouped.length, 1); assert.equal(grouped[0].count, 2);
  assert.equal(grouped[0].failures, 1); assert.equal(grouped[0].status, 'completed');
  assert.equal(events.length, 4); assert.equal(events[1].status, 'failed');
});

test('three real usage checks retain two failures when the last check completes', async () => {
  const { groupActivity } = await import('../lib/activity.ts');
  const events = (['failed','failed','completed'] as const).flatMap(status => [
    { action:'usage_terms',label:'Checking resource usage terms',status:'started' as const },
    { action:'usage_terms',label:'Checking resource usage terms',status },
  ]);
  const [activity] = groupActivity(events);
  assert.equal(activity.count,3);assert.equal(activity.failures,2);assert.equal(activity.status,'completed');
  assert.equal(events.filter(e=>e.status==='failed').length,2);
});
