/**
 * P13-1 fix-3: Browser DOM verification via Playwright.
 *
 * When Playwright is unavailable, outputs BLOCKED JSON and exits 2.
 * Never falls back to source-code checks.  All assertions are real DOM queries.
 *
 * Usage: node scripts/p13_1_browser_verify.js [--port 8000]
 */
'use strict';

const PORT = process.argv.includes('--port')
  ? process.argv[process.argv.indexOf('--port') + 1]
  : '8000';
const BASE = `http://localhost:${PORT}`;

async function main() {
  let playwright;
  try {
    playwright = require('playwright');
  } catch {
    const result = {
      status: 'BLOCKED',
      reason: 'Playwright not available',
      passed: false,
    };
    console.log(JSON.stringify(result));
    process.exit(2);
  }

  const browser = await playwright.chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  let allPassed = true;
  let signals = {};
  let pipeline = {};

  try {
    // --- Signals page ---
    await page.goto(`${BASE}/#signals`);
    await page.waitForTimeout(2000);

    signals = await page.evaluate(() => {
      const body = document.body.innerText;
      const pipeConf = document.getElementById('pipe-confidence');
      return {
        hasUncalibrated: body.includes('未校准'),
        hasModelSelfScoreFilter: body.includes('最低模型自评分'),
        hasBareMinConfidence: body.includes('最低置信度'),
        pipeConfidenceExists: pipeConf !== null,
      };
    });

    const sigPassed = (
      signals.hasUncalibrated === true &&
      signals.hasModelSelfScoreFilter === true &&
      signals.hasBareMinConfidence === false &&
      signals.pipeConfidenceExists === false
    );
    if (!sigPassed) allPassed = false;

    // --- Pipeline page ---
    await page.goto(`${BASE}/#pipeline`);
    await page.waitForTimeout(1500);

    pipeline = await page.evaluate(() => {
      const body = document.body.innerText;
      const pipeConf = document.getElementById('pipe-confidence');
      const hasPrimaryModel = body.includes('DeepSeek') || body.includes('主模型');
      const hasMultimodal = body.includes('多模态') || body.includes('Multimodal');
      const hasAigcProfile = body.includes('AIGC') || body.includes('视频');
      return {
        pipeConfidenceExists: pipeConf !== null,
        visibleConfidenceText: body.includes('最低置信度'),
        hasPrimaryModel,
        hasMultimodal,
        hasAigcProfile,
      };
    });

    const pipePassed = (
      pipeline.pipeConfidenceExists === false &&
      pipeline.visibleConfidenceText === false &&
      pipeline.hasPrimaryModel === true &&
      pipeline.hasMultimodal === true &&
      pipeline.hasAigcProfile === true
    );
    if (!pipePassed) allPassed = false;

  } finally {
    await browser.close();
  }

  const result = { passed: allPassed, signals, pipeline };
  console.log(JSON.stringify(result));
  process.exit(allPassed ? 0 : 1);
}

main().catch((err) => {
  console.log(JSON.stringify({ status: 'ERROR', reason: String(err), passed: false }));
  process.exit(1);
});
