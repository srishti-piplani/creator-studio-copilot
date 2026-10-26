/** Isolated real-provider Phase 4B QA: frontend :3001, backend :8001. */
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const base = 'http://localhost:3001';
const artifacts = '/tmp/creator-studio-phase4b';
await fs.mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(20_000);
const checks = [], responses = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
const nav = name => page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name, exact: true });
async function check(name, run) {
  try { const detail = await run(); checks.push({ name, passed: true, detail }); console.log('PASS', name); }
  catch (error) { checks.push({ name, passed: false, error: error.message }); console.log('FAIL', name, error.message); await page.screenshot({ path: `${artifacts}/failure-${checks.length}.png`, fullPage: false }); }
}
async function send(question) {
  const pending = page.waitForResponse(r => r.url().endsWith('/chat') && r.request().method() === 'POST', { timeout: 240_000 });
  await page.getByLabel('Ask your studio assistant').fill(question);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  let response = await pending;
  for (let attempt = 0; response.status() === 503 && attempt < 1; attempt++) {
    await page.getByRole('button', { name: 'Retry message', exact: true }).waitFor();
    const retried = page.waitForResponse(r => r.url().endsWith('/chat') && r.request().method() === 'POST', { timeout: 240_000 });
    await page.getByRole('button', { name: 'Retry message', exact: true }).click();
    response = await retried;
  }
  assert.equal(response.status(), 200, 'Real backend did not return a usable response');
  const body = await response.json();
  responses.push({ question, response: body, maxParagraphCharacters: Math.max(...body.answer.split(/\n\s*\n/).map(p => p.length)), request: response.request().postDataJSON() });
  await page.getByRole('status').filter({ hasText: 'Working on your request' }).waitFor({ state: 'hidden', timeout: 30_000 });
  return body;
}
try {
  await page.goto(base);
  await page.locator('.landing-setup-card h3').filter({ hasText: 'Audio-Technica AT2035' }).waitFor();
  await check('Landing flow, four setup cards, defaults and readable text at laptop/desktop/mobile widths', async () => {
    const geometry = [];
    for (const [width, height] of [[1280,800], [1366,900], [1920,1080], [390,844]]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(() => scrollTo(0,0));
      const result = await page.evaluate(() => {
        const rect = selector => document.querySelector(selector).getBoundingClientRect();
        return { cards: document.querySelectorAll('.landing-setup-card').length,
          modeBottom: rect('.mode-grid').bottom, setupTop: rect('.landing-setup').top,
          setupBottom: rect('.landing-setup').bottom, composerTop: rect('.composer-zone').top,
          position: getComputedStyle(document.querySelector('.composer-zone')).position,
          overflow: document.documentElement.scrollWidth > innerWidth,
          navFont: getComputedStyle(document.querySelector('.nav-link')).fontSize };
      });
      assert.equal(result.cards, 4); assert.ok(result.setupTop >= result.modeBottom);
      assert.ok(result.composerTop >= result.setupBottom); assert.equal(result.position, 'static'); assert.equal(result.overflow, false);
      geometry.push({ width, height, ...result });
      await page.screenshot({ path: `${artifacts}/landing-${width}.png`, fullPage: false });
    }
    await page.setViewportSize({ width: 1366, height: 900 });
    assert.ok((await page.locator('.landing-setup').innerText()).includes('2nd Gen'));
    assert.ok((await page.locator('.landing-setup').innerText()).includes('Documentation version 12.3'));
    return geometry;
  });
  await check('Saved setup updates the four-card panel and survives refresh', async () => {
    await page.locator('.landing-setup-heading').getByRole('link', { name: 'Edit My Studio Setup' }).click();
    await page.getByRole('button', { name: 'AUDIO-TECHNICA AT2020 XLR condenser microphone', exact: true }).click();
    await page.getByRole('button', { name: 'FOCUSRITE Scarlett Solo 4th Gen', exact: true }).click();
    await page.getByRole('button', { name: 'Save setup', exact: true }).click();
    await nav('Studio Assistant').click();
    await page.locator('.landing-setup-card h3').filter({ hasText: 'Audio-Technica AT2020' }).waitFor();
    await page.reload();
    await page.locator('.landing-setup-card h3').filter({ hasText: 'Focusrite Scarlett Solo' }).waitFor();
    assert.ok((await page.locator('.landing-setup').innerText()).includes('4th Gen'));
    return 'Previously saved selections override new-user defaults.';
  });
  await check('Real beginner Learn, research actions, Notebook follow-up title inheritance', async () => {
    const original = 'What is the difference between EQ and compression?';
    const first = await send(original);
    assert.equal(first.intent, 'learn'); assert.ok(first.citations.length > 0);
    assert.ok(first.activities.some(a => a.action === 'studio_search' && a.status === 'completed'));
    assert.equal(first.activities.some(a => a.action === 'web_search'), false);
    await page.getByRole('button', { name: 'Save Answer', exact: true }).last().click();
    const follow = await send('Can you explain it more simply?');
    assert.equal(follow.session_id, first.session_id);
    await page.getByRole('button', { name: 'Save Answer', exact: true }).last().click();
    await page.locator('.research-panel').last().locator('summary').click();
    await page.screenshot({ path: `${artifacts}/learn-research.png`, fullPage: false });
    await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
    await nav('My Studio Notebook').click();
    await page.locator('.notebook-card h2').first().waitFor();
    const titles = await page.locator('.notebook-card h2').allTextContents();
    assert.equal(titles.filter(t => t === original).length, 2);
    await page.locator('.notebook-open').first().click();
    assert.ok((await page.locator('.notebook-reader').innerText()).includes('Can you explain it more simply?'));
    page.once('dialog', dialog => dialog.accept('EQ and compression — a simple explanation'));
    await page.getByRole('button', { name: 'Edit saved title' }).click();
    await page.getByRole('heading', { name: 'EQ and compression — a simple explanation' }).waitFor();
    return { original, titles, citations: first.citations.length };
  });
  await check('New conversation preserves history; reopen and refresh retain transcript/session', async () => {
    await nav('Studio Assistant').click();
    const firstTitle = 'What is the difference between EQ and compression?';
    const session = await page.evaluate(() => JSON.parse(localStorage.getItem('creator-studio:history:v1'))[0].sessionId);
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    await page.getByRole('heading', { name: 'What would you like to work on?' }).waitFor();
    await page.locator('.recent-conversations').getByRole('link', { name: firstTitle, exact: true }).click();
    assert.equal(await page.locator('.message-user').count(), 2);
    await page.reload();
    await page.locator('.message-user').first().waitFor();
    const active = await page.evaluate(() => {
      const id = JSON.parse(localStorage.getItem('creator-studio:active:v1'));
      return JSON.parse(localStorage.getItem('creator-studio:history:v1')).find(r => r.id === id);
    });
    assert.equal(active.sessionId, session); assert.equal(active.messages.length, 4);
    await page.waitForFunction(() => {
      const last = [...document.querySelectorAll('.message')].at(-1).getBoundingClientRect();
      return last.bottom <= document.querySelector('.composer-zone').getBoundingClientRect().top + 1;
    }, null, { timeout: 8000 });
    const geometry = await page.evaluate(() => {
      const last = [...document.querySelectorAll('.message')].at(-1).getBoundingClientRect();
      const composer = document.querySelector('.composer-zone').getBoundingClientRect();
      return { lastBottom: last.bottom, composerTop: composer.top, answerFont: getComputedStyle(document.querySelector('.prose')).fontSize };
    });
    assert.ok(geometry.lastBottom <= geometry.composerTop + 1, `Message border exceeds composer boundary: ${JSON.stringify(geometry)}`);
    assert.ok(parseFloat(geometry.answerFont) >= 15);
    return geometry;
  });
  await check('Real Logic Pro how-to includes supported steps and success verification or explicit limitation', async () => {
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    const body = await send('How do I add an audio track in Logic Pro? Please give the complete procedure and how to check it worked.');
    assert.equal(body.intent, 'learn');
    assert.ok(body.activities.some(a => a.action === 'web_search'));
    const complete = body.answer.includes('## Steps') && body.answer.includes('## Check it worked');
    assert.ok(complete || body.troubleshooting_status === 'unsupported' || body.diagnostic_question, 'Incomplete how-to not disclosed');
    await page.screenshot({ path: `${artifacts}/logic-howto.png`, fullPage: false });
    return { completeProcedure: complete, status: body.troubleshooting_status, activities: body.activities };
  });
  await check('Equipment-aware real diagnosis uses current defaults and retains failures', async () => {
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    const first = await send('My AT2035 has no recorded signal in Logic Pro. I am using a Scarlett 2i2 2nd Gen today, not the Solo. Give one supported next step or one diagnostic question.');
    assert.equal(first.intent, 'troubleshoot');
    const session = await context.request.get(`http://localhost:8001/sessions/${first.session_id}`);
    const state = await session.json();
    assert.ok(state.equipment.some(p => p.includes('AT2035')));
    assert.equal(state.equipment.some(p => p.includes('AT2020')), false);
    if (first.troubleshooting_status === 'awaiting_outcome') {
      const follow = await send("That didn't work. The recording is still silent.");
      assert.equal(follow.session_id, first.session_id);
    }
    return { equipment: state.equipment, status: first.troubleshooting_status, diagnosticQuestion: first.diagnostic_question };
  });
  await check('Real Discover resources are relevant, licensed honestly, and researched without saved-gear noise', async () => {
    await page.getByRole('button', { name: 'New conversation', exact: true }).click();
    const result = await send('Find tabla loops for a music cover. Clearly label any unknown license permissions.');
    assert.equal(result.intent, 'discover');
    assert.ok(result.activities.some(a => a.action === 'web_search' && a.status === 'completed'));
    assert.equal(result.activities.some(a => a.action === 'studio_search'), false);
    assert.ok(result.resource_cards.length > 0 || result.troubleshooting_status === 'unsupported');
    assert.ok(result.resource_cards.every(r => r.license === 'License not verified.'));
    return { resources: result.resource_cards.length, status: result.troubleshooting_status };
  });
  await check('Existing Notebook/history survive migration and expired sessions remain read-only until new chat', async () => {
    const stored = await page.evaluate(() => ({ history: JSON.parse(localStorage.getItem('creator-studio:history:v1')), notebook: JSON.parse(localStorage.getItem('creator-studio:notebook:v1')) }));
    const migrated = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const old = stored.history.find(r => r.messages.length);
    await migrated.addInitScript(({ old, notebook }) => {
      if (localStorage.getItem('test:migration')) return;
      localStorage.setItem('creator-studio:conversation:v1', JSON.stringify(old));
      localStorage.setItem('creator-studio:notebook:v1', JSON.stringify(notebook));
      localStorage.setItem('creator-studio:setup:v1', JSON.stringify({ microphone: null, audioInterface: null }));
      localStorage.setItem('test:migration', '1');
    }, { old: { ...old, sessionId: '00000000-0000-0000-0000-000000000000' }, notebook: stored.notebook });
    const other = await migrated.newPage();
    await other.goto(base);
    await other.getByText('This session has expired.', { exact: true }).waitFor();
    assert.equal(await other.getByLabel('Ask your studio assistant').isDisabled(), true);
    const contents = await other.evaluate(() => ({ history: JSON.parse(localStorage.getItem('creator-studio:history:v1')), notebook: JSON.parse(localStorage.getItem('creator-studio:notebook:v1')), setup: JSON.parse(localStorage.getItem('creator-studio:setup:v1')) }));
    assert.ok(contents.history.length > 0); assert.equal(contents.notebook.length, stored.notebook.length);
    assert.equal(contents.setup.microphone, null);
    await other.getByRole('button', { name: 'Start new conversation', exact: true }).click();
    await other.locator('.landing-setup-card h3').filter({ hasText: 'No microphone selected' }).waitFor();
    await migrated.close();
    return 'Migrated real stored answers; explicit cleared setup preserved; expired graph state not impersonated.';
  });
  await check('Delete conversation preserves Notebook and mobile history is usable', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.mobile-history summary').click();
    const count = await page.locator('.mobile-history > div').count();
    page.once('dialog', d => d.accept());
    await page.locator('.mobile-history button').first().click();
    assert.equal(await page.locator('.mobile-history > div').count(), count - 1);
    await page.reload();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    const notebook = await page.evaluate(() => JSON.parse(localStorage.getItem('creator-studio:notebook:v1')));
    assert.ok(notebook.length >= 2);
    return { remainingThreads: count - 1, savedAnswers: notebook.length };
  });
} finally {
  await fs.writeFile('../evaluations/phase4b_browser_results.json', JSON.stringify({ checks, responses, browserErrors: errors, screenshots: artifacts, realProviders: true, ports: { frontend: 3001, backend: 8001 } }, null, 2) + '\n');
  await browser.close();
}
if (checks.some(c => !c.passed) || errors.length) process.exitCode = 1;
