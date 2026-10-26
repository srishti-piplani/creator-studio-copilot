/** Phase 4F: real rendered measurements only. No backend or chat requests. */
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const base = process.env.LAYOUT_PREVIEW_URL || 'http://localhost:3001';
const screenshots = '/tmp/creator-studio-phase4f';
await fs.mkdir(screenshots, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
});
const context = await browser.newContext();
const page = await context.newPage();
const browserErrors = [];
page.on('pageerror', error => browserErrors.push(error.message));
const measurements = [];
let conversation;
const round = value => Math.round(value * 100) / 100;
try {
  for (const [width, height] of [[1920, 1080], [1600, 900], [1440, 900], [1280, 800]]) {
    await page.setViewportSize({ width, height });
    await page.goto(base);
    await page.locator('.landing-setup-card h3').filter({ hasText: 'Audio-Technica AT2035' }).waitFor();
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const row = await page.evaluate(() => {
      const box = selector => document.querySelector(selector).getBoundingClientRect();
      const font = selector => parseFloat(getComputedStyle(document.querySelector(selector)).fontSize);
      const main = box('.main-column'), content = box('.mode-grid');
      const cards = [...document.querySelectorAll('.mode-card')].map(el => el.getBoundingClientRect());
      const setup = box('.landing-setup'), composer = box('.composer');
      const subtitle = box('.welcome-subtitle');
      const overlaps = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
      return {
        sidebarWidth: box('.sidebar').width,
        mainWorkspaceWidth: main.width,
        landingContentWidth: content.width,
        workspaceUsePercent: content.width / main.width * 100,
        headingFontSize: font('.welcome h1'),
        cardWidth: cards[0].width,
        cardTitleFontSize: font('.mode-card h2'),
        bodyFontSize: font('.mode-card p'),
        navigationFontSize: font('.nav-link'),
        setupHeight: setup.height,
        setupProductFontSize: font('.landing-setup-card h3'),
        setupDetailFontSize: font('.landing-setup-card p'),
        composerWidth: composer.width,
        composerFontSize: font('.composer textarea'),
        centeredOffset: Math.abs((content.left + content.right) / 2 - (main.left + main.right) / 2),
        horizontalScrolling: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        overlap: cards.some((a, i) => cards.slice(i + 1).some(b => overlaps(a, b))) || overlaps(content, setup) || overlaps(setup, composer) || overlaps(subtitle, content),
        verticallyStacked: content.bottom <= setup.top && setup.bottom <= composer.top,
        threeCardsInRow: cards.every(card => Math.abs(card.top - cards[0].top) < 1),
        setupProducts: document.querySelectorAll('.landing-setup-card').length,
      };
    });
    assert.equal(row.horizontalScrolling, false);
    assert.equal(row.overlap, false);
    assert.equal(row.verticallyStacked, true);
    assert.equal(row.threeCardsInRow, true);
    assert.equal(row.setupProducts, 4);
    assert.ok(row.centeredOffset <= 1);
    assert.ok(Math.abs(row.composerWidth - row.landingContentWidth) <= 1);
    if (width >= 1600) {
      assert.ok(row.workspaceUsePercent >= 80 && row.workspaceUsePercent <= 85);
      assert.ok(row.headingFontSize >= 48 && row.headingFontSize <= 56);
      assert.ok(row.bodyFontSize >= 16);
      assert.ok(row.navigationFontSize >= 15);
    }
    if (width === 1920) {
      assert.ok(row.landingContentWidth >= 1250 && row.landingContentWidth <= 1400);
      assert.ok(row.workspaceUsePercent >= 75);
    }
    measurements.push({ viewport: `${width}x${height}`, ...Object.fromEntries(Object.entries(row).map(([key, value]) => [key, typeof value === 'number' ? round(value) : value])) });
    await page.screenshot({ path: `${screenshots}/landing-${width}.png`, fullPage: true });
    console.log(JSON.stringify(measurements.at(-1)));
  }
  // A labeled typography fixture probes only the conversation CSS; no AI answer,
  // session, stored conversation, transport or application behavior is simulated.
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(base);
  await page.locator('.landing-setup-card h3').filter({ hasText: 'Audio-Technica AT2035' }).waitFor();
  conversation = await page.evaluate(() => {
    const outer = document.querySelector('.assistant-workspace');
    outer.classList.add('conversation-active');
    const panel = document.createElement('div');
    panel.className = 'assistant-message';
    const text = document.createElement('div');
    text.className = 'prose';
    text.textContent = 'Layout-only typography fixture, not an assistant answer. '.repeat(20);
    panel.append(text); outer.append(panel);
    const result = { outerWidth: outer.getBoundingClientRect().width,
      panelWidth: panel.getBoundingClientRect().width, textWidth: text.getBoundingClientRect().width,
      textFontSize: parseFloat(getComputedStyle(text).fontSize) };
    panel.remove();
    return result;
  });
  assert.ok(conversation.outerWidth >= 1200);
  assert.ok(conversation.textWidth < conversation.panelWidth);
  assert.ok(conversation.textWidth < 900);
  assert.deepEqual(browserErrors, []);
} finally {
  await fs.writeFile('../evaluations/phase4f_layout_measurements.json', JSON.stringify({
    browser: 'Installed Google Chrome through Playwright Core', zoom: '100% (no CSS zoom/scale)',
    measurements, conversationCssProbe: conversation, browserErrors, screenshots,
  }, null, 2) + '\n');
  await browser.close();
}
