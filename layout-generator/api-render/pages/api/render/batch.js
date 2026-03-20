import formidable from 'formidable';
import { launch } from 'puppeteer';
import archiver from 'archiver';
import { logger, getRequestContext } from '../../../lib/logger';
import { promises as fs } from 'fs';

export const config = { 
  api: { bodyParser: false },
  maxDuration: 300 // 5 minutes (max for Vercel Pro, use 60 for Hobby)
};

/**
 * Scans a JSON template and rewrites absolute http(s) URLs for images and fonts
 * to use the local image proxy. This avoids CORS issues in Puppeteer.
 * @param {object} json The original JSON template object.
 * @returns {object} The transformed JSON object with proxied URLs.
 */
function transformUrlsToProxy(json) {
  if (!json?.data?.children || !Array.isArray(json.data.children)) {
    return json;
  }
  const newChildren = json.data.children.map(child => {
    const newChild = { ...child };
    const keysToProxy = ['src', 's3FilePath'];
    for (const key of keysToProxy) {
      const url = newChild[key];
      if (typeof url === 'string' && url.startsWith('http')) {
        newChild[key] = `/api/image_proxy?url=${encodeURIComponent(url)}`;
      }
    }
    if (newChild.svgElement && typeof newChild.svgElement.svgUrl === 'string' && newChild.svgElement.svgUrl.startsWith('http')) {
      newChild.svgElement = {
        ...newChild.svgElement,
        svgUrl: `/api/image_proxy?url=${encodeURIComponent(newChild.svgElement.svgUrl)}`
      };
    }
    return newChild;
  });
  return { ...json, data: { ...json.data, children: newChildren } };
}

/**
 * Renders a single file using a given browser instance.
 * @param {import('puppeteer').Browser} browser - The Puppeteer browser instance.
 * @param {string} baseUrl - The base URL of the application.
 * @param {import('formidable').File} file - The formidable file object.
 * @returns {Promise<{name: string, buffer: Buffer}|null>}
 */
async function renderFile(browser, baseUrl, file) {
  try {
    const text = await fs.readFile(file.filepath, 'utf8');
    let json = JSON.parse(text);

    if (json && typeof json === 'object' && !('data' in json)) {
      json = { data: json };
    }
    
    const proxiedJson = transformUrlsToProxy(json);
    const page = await browser.newPage();
    
    try {
      page.on('console', msg => logger.debug('page.console', { type: msg.type(), text: msg.text() }));
      page.on('pageerror', err => logger.error('page.error', err, { filename: file.originalFilename }));
      
      await page.setViewport({ width: 1200, height: 1200, deviceScaleFactor: 1 });
      await page.goto(`${baseUrl}/renderer.html?headless=1`, { waitUntil: 'networkidle0' });
      
  const payload = await page.evaluate(json => window.__renderAndGetDataURL(json), proxiedJson);
  const dataUrl = typeof payload === 'string' ? payload : payload?.dataUrl;
  if (!dataUrl) throw new Error('Renderer did not return an image payload');

  const buffer = dataUrlToBuffer(dataUrl);
      const outName = (file.originalFilename || `render.json`).replace(/\.json$/i, '.png');
      
      return { name: outName, buffer };
    } finally {
      await page.close();
    }
  } catch (err) {
    logger.error('api.render.batch.renderFile', err, { filename: file.originalFilename });
    return null; // Return null to indicate failure for this file
  }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end('Method not allowed');

  const form = formidable({ multiples: true, maxFileSize: 10 * 1024 * 1024 });

  let files;
  try {
    const parsed = await new Promise((resolve, reject) => {
      form.parse(req, (err, fields, files) => err ? reject(err) : resolve(files));
    });
    files = parsed;
  } catch (err) {
    logger.error('api.render.batch.formidable', err, { req: getRequestContext(req) });
    return res.status(400).end('Invalid form data');
  }

  const fileList = Array.isArray(files.files) ? files.files : [files.files].filter(Boolean);
  if (!fileList.length) return res.status(400).end('No files');

  let browser;
  try {
    browser = await launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--font-render-hinting=medium'],
    });

    const baseUrl = `http://${req.headers.host}`;

    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', 'attachment; filename="renders.zip"');
    const archive = archiver('zip');
    archive.on('error', (err) => {
      logger.error('api.render.batch.archive', err);
      throw err;
    });
    archive.pipe(res);

    const renderPromises = fileList.map(file => renderFile(browser, baseUrl, file));
    const renderedFiles = await Promise.all(renderPromises);

    for (const file of renderedFiles) {
      if (file) { // Only append successfully rendered files
        archive.append(file.buffer, { name: file.name });
      }
    }

    await archive.finalize();
  } catch (e) {
    logger.error('api.render.batch', e, { req: getRequestContext(req) });
    if (!res.headersSent) res.status(500).end('Render failed');
  } finally {
    if (browser) await browser.close();
  }
}

function dataUrlToBuffer(dataUrl) {
  const [, base64] = dataUrl.split(',');
  return Buffer.from(base64, 'base64');
}