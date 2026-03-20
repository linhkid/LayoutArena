/**
 * Test script for local image serving
 * Usage: node test-local-image.js <path-to-image>
 * Example: node test-local-image.js /var/folders/screenshot.png
 */

const fs = require('fs');
const path = require('path');

// Get image path from command line argument
const imagePath = process.argv[2];

if (!imagePath) {
  console.error('Usage: node test-local-image.js <path-to-image>');
  console.error('Example: node test-local-image.js /var/folders/screenshot.png');
  process.exit(1);
}

console.log('Testing local image serving...\n');
console.log(`Image path: ${imagePath}\n`);

// Check if file exists
if (!fs.existsSync(imagePath)) {
  console.error(`❌ File not found: ${imagePath}`);
  process.exit(1);
}
console.log('✓ File exists');

// Check if it's a file
const stats = fs.statSync(imagePath);
if (!stats.isFile()) {
  console.error(`❌ Path is not a file: ${imagePath}`);
  process.exit(1);
}
console.log('✓ Path is a file');

// Check read permissions
try {
  fs.accessSync(imagePath, fs.constants.R_OK);
  console.log('✓ File is readable');
} catch (err) {
  console.error(`❌ File is not readable: ${err.message}`);
  process.exit(1);
}

// Get file info
console.log(`\nFile info:`);
console.log(`  Size: ${(stats.size / 1024).toFixed(2)} KB`);
console.log(`  Modified: ${stats.mtime.toISOString()}`);

// Create test JSON with the image
const testLayout = {
  data: {
    width: 1080,
    height: 1080,
    background: '#ffffff',
    children: [
      {
        id: 'test-image',
        type: 'image',
        src: imagePath,
        x: 0,
        y: 0,
        width: 1080,
        height: 1080,
        cropWidth: 1,
        cropHeight: 1,
        cropX: 0,
        cropY: 0,
        rotation: 0,
        opacity: 1,
        visible: true
      }
    ]
  }
};

// Show the test JSON
console.log(`\nTest JSON layout:`);
console.log(JSON.stringify(testLayout, null, 2));

// Show the curl command
console.log(`\n${'='.repeat(60)}`);
console.log('To test with the API, run:');
console.log(`${'='.repeat(60)}\n`);

const curlCommand = `curl -X POST http://localhost:3000/api/render/preview \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(testLayout)}' \\
  --output test-output.png`;

console.log(curlCommand);

console.log(`\n${'='.repeat(60)}`);
console.log('Or to get the data URL:');
console.log(`${'='.repeat(60)}\n`);

const curlDataUrlCommand = `curl -X POST http://localhost:3000/api/render/preview \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(testLayout)}'`;

console.log(curlDataUrlCommand);

console.log(`\n${'='.repeat(60)}`);
console.log('To access the image directly through the proxy:');
console.log(`${'='.repeat(60)}\n`);

const proxyUrl = `http://localhost:3000/api/local_image?path=${encodeURIComponent(imagePath)}`;
console.log(`curl "${proxyUrl}" --output direct-image.png`);

console.log(`\n✅ All checks passed! The image should work with the renderer.\n`);
