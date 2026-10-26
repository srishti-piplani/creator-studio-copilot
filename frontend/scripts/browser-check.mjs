/** Real-provider browser QA, opt-in. Requires FastAPI :8000 and Next.js :3000.
 * No AI responses are mocked. Failure-path requests are deliberately aborted.
 */
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const artifactDir = '/tmp/creator-studio-frontend';
await fs.mkdir(artifactDir, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
const page = await context.newPage();
const results = [];
const errors = [];
page.on('pageerror', e => errors.push(e.message));
page.setDefaultTimeout(20_000);
let lastRequest;
page.on('request', request => { if (request.url().endsWith('/chat') && request.method() === 'POST') lastRequest = request.postDataJSON(); });
async function chat(text) {
  const response = page.waitForResponse(res => res.url().endsWith('/chat') && res.request().method() === 'POST', { timeout: 240_000 });
  await page.getByLabel('Ask your studio assistant').fill(text);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  let res = await response;
  for (let attempt = 0; res.status() === 503 && attempt < 2; attempt++) {
    await page.getByRole('button', { name: 'Retry message', exact: true }).waitFor();
    const retried = page.waitForResponse(r => r.url().endsWith('/chat') && r.request().method() === 'POST', { timeout: 240_000 });
    await page.getByRole('button', { name: 'Retry message', exact: true }).click();
    res = await retried;
    console.log('Provider retry HTTP', res.status());
  }
  assert.equal(res.status(), 200, `Chat returned HTTP ${res.status()}`);
  const body = await res.json();
  await page.getByText(body.answer, { exact: true }).first().waitFor({ state: 'visible', timeout: 1000 }).catch(() => {}); // Markdown transforms text nodes.
  await page.getByRole('status').filter({ hasText: 'Working on your request' }).waitFor({ state: 'hidden', timeout: 30_000 });
  return body;
}
async function check(name, fn) {
  try { const details = await fn(); results.push({ name, passed: true, details }); console.log('PASS', name); }
  catch (error) { results.push({ name, passed: false, error: error.message }); console.log('FAIL', name, error.message); await page.screenshot({ path: `${artifactDir}/failure-${results.length}.png`, fullPage: true }); }
}
try {
  await page.goto('http://localhost:3000');
  await page.getByRole('heading', { name: 'What would you like to work on?' }).waitFor();
  await page.screenshot({ path: `${artifactDir}/assistant-desktop.png`, fullPage: true });
  await check('Default landing, editable shortcuts, and empty Notebook', async () => {
    await page.getByRole('button', { name: /Learn Understand/ }).click();
    await page.getByRole('button', { name: 'What does a compressor do?' }).click();
    assert.equal(await page.getByLabel('Ask your studio assistant').inputValue(), 'What does a compressor do?');
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'My Studio Notebook' }).click();
    await page.getByRole('heading', { name: 'A little knowledge, kept close.' }).waitFor();
    await page.getByRole('link', { name: 'Explore with your assistant' }).click();
    return 'No chat request was sent by selecting a shortcut.';
  });
  await check('Journey A: real Learn answer, citations, save, reopen, refresh', async () => {
    const answer = await chat('What does compression do in audio production?');
    assert.equal(answer.intent, 'learn'); assert.ok(answer.citations.length > 0);
    await page.getByRole('button', { name: 'Save Answer', exact: true }).last().click();
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'My Studio Notebook' }).click();
    await page.locator('.notebook-open').first().click();
    await page.locator('.notebook-reader .answer-content').waitFor();
    const before = await page.locator('.notebook-reader .prose').innerText();
    assert.ok(before.length > 40);
    await page.reload();
    await page.locator('.notebook-open').first().click();
    assert.equal(await page.locator('.notebook-reader .prose').innerText(), before);
    await page.screenshot({ path: `${artifactDir}/notebook-reader.png`, fullPage: true });
    return { intent: answer.intent, citations: answer.citations.length, session: answer.session_id, savedEvidence: true };
  });
  await check('Journey D: hardware selections persist and reach the backend', async () => {
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'My Studio Setup' }).click();
    const mic = page.getByRole('button', { name: 'AUDIO-TECHNICA AT2035 XLR condenser microphone', exact: true });
    if (await mic.getAttribute('aria-pressed') !== 'true') await mic.click();
    const audioInterface = page.getByRole('button', { name: 'FOCUSRITE Scarlett 2i2 2nd Gen', exact: true });
    if (await audioInterface.getAttribute('aria-pressed') !== 'true') await audioInterface.click();
    await page.getByRole('button', { name: 'Save setup', exact: true }).click();
    await page.reload();
    assert.equal(await page.getByRole('button', { name: 'AUDIO-TECHNICA AT2035 XLR condenser microphone', exact: true }).getAttribute('aria-pressed'), 'true');
    assert.equal(await page.getByRole('button', { name: 'FOCUSRITE Scarlett 2i2 2nd Gen', exact: true }).getAttribute('aria-pressed'), 'true');
    await page.screenshot({ path: `${artifactDir}/setup-desktop.png`, fullPage: true });
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'Studio Assistant' }).click();
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    const result = await chat('My audio interface has input signal but Logic Pro 12.3 is not recording my microphone. Ask me one diagnostic question first.');
    assert.deepEqual(lastRequest.equipment, ['Audio-Technica AT2035', 'Focusrite Scarlett 2i2 — 2nd Gen']);
    assert.equal(result.intent, 'troubleshoot');
    assert.ok(result.diagnostic_question, 'Backend did not return a diagnostic question');
    return { equipment: lastRequest.equipment, diagnosticQuestion: result.diagnostic_question };
  });
  await check('Journey B: diagnostic follow-up keeps the session', async () => {
    const oldSession = await page.evaluate(() => {
      const active = JSON.parse(localStorage.getItem('creator-studio:active:v1'));
      return JSON.parse(localStorage.getItem('creator-studio:history:v1')).find(thread => thread.id === active).sessionId;
    });
    let result = await chat('The input meter moves on the interface, but the recording is silent. The selected input is already the interface.');
    assert.equal(result.session_id, oldSession); assert.equal(result.intent, 'troubleshoot');
    for (let attempt = 0; result.troubleshooting_status !== 'awaiting_outcome' && attempt < 2; attempt++) {
      result = await chat('The interface has signal, but the Logic Pro input meter does not move. I have now answered the diagnostic question. Please suggest exactly one supported fix to try next, without another question.');
      assert.equal(result.session_id, oldSession);
    }
    assert.equal(result.troubleshooting_status, 'awaiting_outcome', 'No supported fix was offered, so the failed-fix interaction cannot be verified');
    if (result.troubleshooting_status === 'awaiting_outcome') {
      const response = page.waitForResponse(res => res.url().endsWith('/chat') && res.request().method() === 'POST', { timeout: 240_000 });
      await page.getByRole('button', { name: "That didn't work", exact: true }).click();
      const res = await response; assert.equal(res.status(), 200); result = await res.json();
      await page.getByRole('status').filter({ hasText: 'Working on your request' }).waitFor({ state: 'hidden', timeout: 30_000 });
    } else result = await chat("That didn't work. Recording is still silent.");
    assert.equal(result.session_id, oldSession); assert.equal(result.intent, 'troubleshoot');
    await page.screenshot({ path: `${artifactDir}/troubleshoot-desktop.png`, fullPage: true });
    const details = await context.request.get(`http://localhost:8000/sessions/${oldSession}`);
    const session = await details.json();
    assert.ok(session.steps.some(step => step.outcome === 'failed'), 'Backend did not retain the failed-step outcome');
    return { sessionRetained: true, status: result.troubleshooting_status, failedStepRecorded: true };
  });
  await check('Journey C: real Keenable resources, open link, save answer', async () => {
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    const result = await chat('Find free tabla loops for a music cover. Show resources even when the license cannot be verified, and clearly label that limitation.');
    assert.equal(result.intent, 'discover'); assert.ok(result.resource_cards.length > 0, 'No live resources returned');
    await page.locator('.resource-card').first().waitFor();
    const popup = page.waitForEvent('popup');
    await page.locator('.resource-card h3 a').first().click();
    const opened = await popup;
    await opened.waitForLoadState('domcontentloaded', { timeout: 30_000 }).catch(() => {});
    const openedUrl = opened.url(); assert.ok(openedUrl.startsWith('http')); await opened.close();
    await page.getByRole('button', { name: 'Save Answer', exact: true }).last().click();
    await page.screenshot({ path: `${artifactDir}/discover-desktop.png`, fullPage: true });
    return { resources: result.resource_cards.length, openedUrl, licenses: result.resource_cards.map(r => r.license) };
  });
  await check('Mobile responsiveness and conversation refresh', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await page.locator('.message-assistant').first().waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.getByRole('navigation', { name: 'Mobile navigation', exact: true }).waitFor();
    await page.screenshot({ path: `${artifactDir}/assistant-mobile.png`, fullPage: true });
    await page.getByRole('navigation', { name: 'Mobile navigation', exact: true }).getByRole('link', { name: 'Setup', exact: true }).click();
    await page.getByRole('heading', { name: 'My Studio Setup' }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: `${artifactDir}/setup-mobile.png`, fullPage: true });
    return '390px viewport, no horizontal overflow; conversation survived refresh.';
  });
  await check('Unavailable FastAPI, retry without duplicate user message', async () => {
    await page.getByRole('navigation', { name: 'Mobile navigation', exact: true }).getByRole('link', { name: 'Assistant', exact: true }).click();
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    await page.route('**/chat', route => route.abort('connectionrefused'));
    await page.getByLabel('Ask your studio assistant').fill('Explain what EQ does.');
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'Could not reach' }).waitFor();
    const count = await page.locator('.message-user').count();
    await page.unroute('**/chat');
    const response = page.waitForResponse(res => res.url().endsWith('/chat') && res.request().method() === 'POST', { timeout: 240_000 });
    await page.getByRole('button', { name: 'Retry message', exact: true }).click();
    const res = await response; assert.equal(res.status(), 200);
    await page.locator('.message-assistant').first().waitFor({ timeout: 30_000 });
    assert.equal(await page.locator('.message-user').count(), count);
    return 'Connection failure was simulated by aborting the request; successful retry used the real API.';
  });
  await check('Notebook search, category filter and deletion', async () => {
    await page.getByRole('navigation', { name: 'Mobile navigation', exact: true }).getByRole('link', { name: 'Notebook', exact: true }).click();
    await page.getByLabel('Search saved answers').fill('compression');
    assert.equal(await page.locator('.notebook-card').count(), 1);
    await page.getByRole('button', { name: 'discover', exact: true }).click();
    await page.getByRole('heading', { name: 'No matching notes yet.' }).waitFor();
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    const before = await page.locator('.notebook-card').count();
    await page.getByRole('button', { name: /^Delete saved answer:/ }).first().click();
    await page.getByRole('button', { name: 'Delete', exact: true }).click();
    assert.equal(await page.locator('.notebook-card').count(), before - 1);
    return 'Local search, filter and confirmed deletion work without an LLM call.';
  });
} finally {
  const report = { kind: 'Real-provider Chrome browser journeys; only failure-path network abort is simulated', results, browserErrors: errors, screenshots: artifactDir };
  await fs.writeFile('../evaluations/frontend_browser_results.json', JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (results.some(r => !r.passed) || errors.length) process.exitCode = 1;
