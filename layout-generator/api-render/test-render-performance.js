const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

async function testRenderPerformance() {
  console.log('Starting performance test...\n');

  const layoutPath = path.join(__dirname, '../data/case_10/layout.json');
  const layoutData = JSON.parse(fs.readFileSync(layoutPath, 'utf8'));

  const timings = {};
  const start = Date.now();

  // Launch browser
  const browserStart = Date.now();
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  timings.browserLaunch = Date.now() - browserStart;

  // Create page
  const pageStart = Date.now();
  const page = await browser.newPage();
  timings.pageCreate = Date.now() - pageStart;

  // Collect console logs
  const consoleLogs = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push(`[${msg.type()}] ${text}`);
  });

  // Navigate to renderer
  const navStart = Date.now();
  await page.goto('http://localhost:3000/renderer.html?headless=1', {
    waitUntil: 'networkidle0',
  });
  timings.pageLoad = Date.now() - navStart;

  // Execute render
  const renderStart = Date.now();
  const result = await page.evaluate(async (json) => {
    const start = performance.now();
    const output = await window.__renderAndGetDataURL(json);
    const end = performance.now();
    return {
      output,
      renderTime: end - start,
    };
  }, layoutData);
  timings.renderExecute = Date.now() - renderStart;
  timings.renderTimeInBrowser = result.renderTime;

  await browser.close();

  timings.total = Date.now() - start;

  // Print results
  console.log('=== Performance Breakdown ===');
  console.log(`Browser Launch:     ${timings.browserLaunch}ms`);
  console.log(`Page Creation:      ${timings.pageCreate}ms`);
  console.log(`Page Load:          ${timings.pageLoad}ms`);
  console.log(`Render Execute:     ${timings.renderExecute}ms`);
  console.log(`  (in-browser time: ${timings.renderTimeInBrowser.toFixed(2)}ms)`);
  console.log(`---`);
  console.log(`Total:              ${timings.total}ms`);

  // Print cache stats from console logs
  console.log('\n=== Cache Statistics from Browser ===');
  const cacheLines = consoleLogs.filter(log => log.includes('[Cache]'));
  cacheLines.forEach(line => console.log(line));

  // Print any errors or warnings
  const errors = consoleLogs.filter(log =>
    log.includes('[error]') || log.includes('[warn]')
  );
  if (errors.length > 0) {
    console.log('\n=== Errors/Warnings ===');
    errors.slice(0, 10).forEach(line => console.log(line));
  }
}

testRenderPerformance().catch(console.error);
