#!/usr/bin/env node
/**
 * Memory Leak Test Script
 *
 * Tests the rendering endpoint with multiple requests to verify
 * memory leak fixes (blob URL revocation, browser pool recycling).
 *
 * Usage:
 *   1. Start the server: cd api-render && npm run dev
 *   2. Run this script: node test-memory-leak.js
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const NUM_ITERATIONS = parseInt(process.env.ITERATIONS) || 50;
const PARALLEL_REQUESTS = parseInt(process.env.PARALLEL) || 3;

// Find all test JSON files in the data folder
const dataDir = path.join(__dirname, '..', 'data');
const testFiles = [];

function findJsonFiles(dir) {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      findJsonFiles(fullPath);
    } else if (entry.name.endsWith('.json')) {
      testFiles.push(fullPath);
    }
  }
}

findJsonFiles(dataDir);

console.log(`Found ${testFiles.length} test files:`);
testFiles.forEach(f => console.log(`  - ${path.relative(dataDir, f)}`));
console.log();

function getChromeProcessCount() {
  try {
    const result = execSync('ps aux | grep -i "chrome" | grep -v grep | wc -l', { encoding: 'utf8' });
    return parseInt(result.trim());
  } catch {
    return -1;
  }
}

function getChromeMemoryMB() {
  try {
    // Get RSS memory of all Chrome processes in KB, then sum and convert to MB
    const result = execSync(
      'ps aux | grep -i "chrome" | grep -v grep | awk \'{sum += $6} END {print sum}\'',
      { encoding: 'utf8' }
    );
    const kb = parseInt(result.trim()) || 0;
    return Math.round(kb / 1024);
  } catch {
    return -1;
  }
}

async function renderLayout(jsonData, iteration) {
  const startTime = Date.now();
  try {
    const response = await fetch(`${BASE_URL}/api/render/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(jsonData),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`HTTP ${response.status}: ${text.substring(0, 100)}`);
    }

    const result = await response.json();
    const duration = Date.now() - startTime;
    return { success: true, duration, hasDataUrl: !!result.dataUrl };
  } catch (error) {
    const duration = Date.now() - startTime;
    return { success: false, duration, error: error.message };
  }
}

async function runBatch(batchNum, layouts) {
  const promises = layouts.map((layout, idx) => renderLayout(layout, `${batchNum}-${idx}`));
  return Promise.all(promises);
}

async function main() {
  console.log('='.repeat(60));
  console.log('Memory Leak Test - Renderer');
  console.log('='.repeat(60));
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Iterations: ${NUM_ITERATIONS}`);
  console.log(`Parallel requests per batch: ${PARALLEL_REQUESTS}`);
  console.log();

  // Load test data
  const testData = [];
  for (const file of testFiles) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      const json = JSON.parse(content);
      testData.push({ file: path.relative(dataDir, file), data: json });
    } catch (e) {
      console.warn(`Skipping ${file}: ${e.message}`);
    }
  }

  if (testData.length === 0) {
    console.error('No valid test data found!');
    process.exit(1);
  }

  console.log(`Loaded ${testData.length} test layouts\n`);

  // Initial state
  const initialProcesses = getChromeProcessCount();
  const initialMemory = getChromeMemoryMB();
  console.log(`Initial Chrome state:`);
  console.log(`  Processes: ${initialProcesses}`);
  console.log(`  Memory: ${initialMemory} MB`);
  console.log();

  let successCount = 0;
  let failCount = 0;
  let totalDuration = 0;

  console.log('Starting render loop...\n');
  const overallStart = Date.now();

  for (let i = 0; i < NUM_ITERATIONS; i++) {
    // Pick random layouts for this batch
    const batchLayouts = [];
    for (let j = 0; j < PARALLEL_REQUESTS; j++) {
      const randomTest = testData[Math.floor(Math.random() * testData.length)];
      batchLayouts.push(randomTest.data);
    }

    const results = await runBatch(i, batchLayouts);

    for (const result of results) {
      if (result.success) {
        successCount++;
        totalDuration += result.duration;
      } else {
        failCount++;
        console.log(`  ✗ Error: ${result.error}`);
      }
    }

    // Log progress every 10 iterations
    if ((i + 1) % 10 === 0) {
      const currentProcesses = getChromeProcessCount();
      const currentMemory = getChromeMemoryMB();
      const avgDuration = successCount > 0 ? Math.round(totalDuration / successCount) : 0;
      console.log(
        `[${i + 1}/${NUM_ITERATIONS}] ` +
        `Success: ${successCount}, Failed: ${failCount}, ` +
        `Avg: ${avgDuration}ms, ` +
        `Chrome: ${currentProcesses} procs / ${currentMemory} MB`
      );
    }
  }

  const overallDuration = Date.now() - overallStart;

  // Final state
  console.log();
  console.log('='.repeat(60));
  console.log('Results');
  console.log('='.repeat(60));

  const finalProcesses = getChromeProcessCount();
  const finalMemory = getChromeMemoryMB();

  console.log(`Total renders: ${successCount + failCount}`);
  console.log(`  Successful: ${successCount}`);
  console.log(`  Failed: ${failCount}`);
  console.log(`Total time: ${(overallDuration / 1000).toFixed(1)}s`);
  console.log(`Average render time: ${successCount > 0 ? Math.round(totalDuration / successCount) : 0}ms`);
  console.log();
  console.log(`Chrome process change: ${initialProcesses} → ${finalProcesses} (${finalProcesses - initialProcesses >= 0 ? '+' : ''}${finalProcesses - initialProcesses})`);
  console.log(`Chrome memory change: ${initialMemory} MB → ${finalMemory} MB (${finalMemory - initialMemory >= 0 ? '+' : ''}${finalMemory - initialMemory} MB)`);
  console.log();

  // Wait a bit and check again (allow for cleanup)
  console.log('Waiting 10s for cleanup...');
  await new Promise(r => setTimeout(r, 10000));

  const afterCleanupProcesses = getChromeProcessCount();
  const afterCleanupMemory = getChromeMemoryMB();
  console.log(`After cleanup: ${afterCleanupProcesses} procs / ${afterCleanupMemory} MB`);

  if (afterCleanupProcesses > initialProcesses + 3) {
    console.log('\n⚠️  WARNING: Chrome processes may be leaking!');
  } else {
    console.log('\n✓ Chrome process count looks stable');
  }
}

main().catch(console.error);
