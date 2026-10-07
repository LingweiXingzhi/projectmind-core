/* Optional real-browser evidence. Never substitute a DOM mock or HTTP PASS. */
const fs = require('fs');
const path = require('path');
const [baseUrl, output, targetHead] = process.argv.slice(2);
if (!baseUrl || !output || !/^[0-9a-f]{40,64}$/.test(targetHead || '')) {
  throw new Error('Usage: node browser_smoke.js LOOPBACK_ORIGIN NEW_OUTPUT_DIR FULL_TARGET_SHA');
}
const parsed = new URL(baseUrl);
if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname)) {
  throw new Error('Only the explicitly configured local test service is allowed');
}
if (fs.existsSync(output)) throw new Error('Do not overwrite evidence');
fs.mkdirSync(output, {recursive: true});
let browser;
(async () => {
  const report = {targetHead, baseUrl, observer: 'D Playwright participant observation',
    observedAt: new Date().toISOString(), status: 'NOT_RUN',
    scope: 'A_DEVELOPMENT_SAMPLE_UI_ONLY_NOT_REAL_AI_OR_PUBLISH', checks: []};
  try {
    const { chromium } = require('playwright');
    browser = await chromium.launch({headless: true});
    const page = await browser.newPage();
    await page.goto(baseUrl, {waitUntil: 'networkidle'});
    await page.locator('[data-entry="planning"]').click();
    await page.locator('#arch-planning-title').fill('D_TEST_ONLY browser planning');
    await page.locator('#arch-planning-goals').fill('Expected A B C, no source code');
    await page.locator('#arch-create-planning').locator('button[type=submit]').click();
    await page.locator('#arch-sample-button').waitFor({state: 'visible'});
    await page.locator('#arch-sample-button').click();
    await page.getByRole('button', {name: '应用到草稿', exact: false}).click();
    await page.locator('#arch-map-stage button').first().waitFor({state: 'visible'});
    await page.screenshot({path: path.join(output,'planning-sample.png'), fullPage: true});
    report.status = 'OBSERVED_COMPONENT';
    report.checks.push({id: 'T02', status: 'PASS',
      detail: 'Actual browser displayed development sample; not C bootstrap or owner-approved architecture',
      evidence: ['planning-sample.png'], scope: 'UI_COMPONENT_ONLY'});
    await page.reload({waitUntil:'networkidle'});
    await page.screenshot({path: path.join(output,'after-refresh.png'),fullPage:true});
    report.checks.push({id:'T06',status:'NOT_RUN',detail:'Refresh screenshot alone does not prove same draft content persisted',
      evidence:['after-refresh.png']});
  } catch (error) {
    report.status = browser ? 'FAIL' : 'NOT_RUN';
    report.error = String(error.message || error);
    report.checks = [{id:'T02', status: browser ? 'FAIL' : 'NOT_RUN',
      detail:'Real browser prerequisite/navigation failed; no fabricated screenshot', evidence:[]}];
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output,'ui-evidence.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({status:report.status, report:path.join(output,'ui-evidence.json')}));
    process.exitCode = report.status === 'FAIL' ? 1 : report.status === 'NOT_RUN' ? 2 : 0;
  }
})();
