const path = require('path');
const { logger } = require('./logger');
const { fetchGoogleFontUrl, isGoogleFont, parseFontWeight } = require('./fontHelper');

/**
 * Injects Google Fonts URLs for text elements that need them
 * @param {object} json The original JSON template object
 * @returns {Promise<object>} The JSON with Google Font URLs injected
 */
async function injectGoogleFonts(json) {
  if (!json?.data?.children || !Array.isArray(json.data.children)) {
    return json;
  }

  const newChildren = await Promise.all(
    json.data.children.map(async (child) => {
      const newChild = { ...child };

      // Check if this is a text element
      const isTextElement =
        child.type === 'text' ||
        child.elementType === 'headline' ||
        child.elementType === 'cta' ||
        child.class === 'headline';

      if (!isTextElement) {
        return newChild;
      }

      const fontFamily = child.fontFamily || child.displayFontFamily;
      const hasExistingFontUrl = Boolean(child.s3FilePath || child.s3filepath || child.s3filePath);

      // If font is specified and no font URL exists, try to fetch from Google Fonts
      if (fontFamily && !hasExistingFontUrl && isGoogleFont(fontFamily)) {
        try {
          const weight = parseFontWeight(child.fontStyle, child.fontWeight);
          const style = child.fontStyle?.includes('italic') ? 'italic' : 'normal';

          logger.info('renderHelpers.injectGoogleFonts', {
            fontFamily,
            weight,
            style,
            elementId: child.id,
          });

          const fontUrl = await fetchGoogleFontUrl(fontFamily, weight, style);

          if (fontUrl) {
            newChild.s3FilePath = fontUrl;
            logger.info('renderHelpers.injectGoogleFonts.success', {
              fontFamily,
              fontUrl: fontUrl.substring(0, 80) + '...',
            });
          } else {
            logger.warn('renderHelpers.injectGoogleFonts.failed', {
              fontFamily,
              fallback: 'Will use browser default',
            });
          }
        } catch (error) {
          logger.error('renderHelpers.injectGoogleFonts.error', error, {
            fontFamily,
            elementId: child.id,
          });
        }
      }

      return newChild;
    })
  );

  return {
    ...json,
    data: {
      ...json.data,
      children: newChildren,
    },
  };
}

/**
 * Scans a JSON template and rewrites absolute http(s) URLs and local file paths
 * to use the appropriate proxy. This avoids CORS issues in Puppeteer.
 * @param {object} json The original JSON template object.
 * @returns {object} The transformed JSON object with proxied URLs.
 */
function transformUrlsToProxy(json) {
  if (!json?.data?.children || !Array.isArray(json.data.children)) {
    return json;
  }

  const newChildren = json.data.children.map((child) => {
    const newChild = { ...child };
    const keysToProxy = ['src', 's3FilePath'];

    for (const key of keysToProxy) {
      const url = newChild[key];
      if (typeof url === 'string') {
        // Handle remote URLs
        if (url.startsWith('http://') || url.startsWith('https://')) {
          newChild[key] = `/api/image_proxy?url=${encodeURIComponent(url)}`;
        }
        // Handle local absolute file paths
        else if (url.startsWith('/var/') || url.startsWith('/Users/') ||
                 url.startsWith('/home/') || url.startsWith('/tmp/')) {
          newChild[key] = `/api/local_image?path=${encodeURIComponent(url)}`;
        }
      }
    }

    if (newChild.svgElement && typeof newChild.svgElement.svgUrl === 'string') {
      const svgUrl = newChild.svgElement.svgUrl;
      // Handle remote URLs
      if (svgUrl.startsWith('http://') || svgUrl.startsWith('https://')) {
        newChild.svgElement = {
          ...newChild.svgElement,
          svgUrl: `/api/image_proxy?url=${encodeURIComponent(svgUrl)}`,
        };
      }
      // Handle local absolute file paths
      else if (svgUrl.startsWith('/var/') || svgUrl.startsWith('/Users/') ||
               svgUrl.startsWith('/home/') || svgUrl.startsWith('/tmp/')) {
        newChild.svgElement = {
          ...newChild.svgElement,
          svgUrl: `/api/local_image?path=${encodeURIComponent(svgUrl)}`,
        };
      }
    }

    return newChild;
  });

  return {
    ...json,
    data: {
      ...json.data,
      children: newChildren,
    },
  };
}

function normalizeLayout(layout) {
  if (layout && typeof layout === 'object' && !('data' in layout)) {
    return { data: layout };
  }
  return layout;
}

/**
 * Renders a single layout object using a given browser instance.
 * @param {import('puppeteer-core').Browser} browser - The Puppeteer browser instance.
 * @param {string} baseUrl - The base URL of the application.
 * @param {object} layoutJson - The JSON layout object to render.
 * @param {object} options - Additional rendering options.
 * @param {boolean} options.showBoundingBoxes - Whether to draw bounding boxes.
 * @returns {Promise<{dataUrl: string, boundingBoxes: Array, dimensions: {width: number, height: number}|null}>}
 */
async function renderLayout(browser, baseUrl, layoutJson, options = {}) {
  const timings = {};
  const totalStart = Date.now();

  // Step 1: Inject Google Fonts URLs for text elements
  const googleFontsStart = Date.now();
  const jsonWithFonts = await injectGoogleFonts(layoutJson);
  timings.googleFonts = Date.now() - googleFontsStart;

  // Step 2: Transform URLs to proxy
  const transformStart = Date.now();
  const proxiedJson = transformUrlsToProxy(jsonWithFonts);
  timings.transform = Date.now() - transformStart;

  // Step 3: Create new page
  const pageCreateStart = Date.now();
  const page = await browser.newPage();
  timings.pageCreate = Date.now() - pageCreateStart;

  const pageErrors = [];

  try {
    page.on('console', (msg) => {
      const type = msg.type();
      const text = msg.text();
      if (type === 'error' || (type === 'warn' && text.toLowerCase().includes('failed'))) {
        pageErrors.push(`[${type.toUpperCase()}] ${text}`);
      }
      try {
        logger.debug('page.console', { type: msg.type(), text: msg.text() });
      } catch {}
    });
    page.on('pageerror', (err) => {
      pageErrors.push(`[PAGE_ERROR] ${err.message}`);
      logger.error('page.error', err);
    });
    page.on('requestfailed', (reqObj) =>
      logger.warn('page.requestfailed', {
        url: reqObj.url(),
        method: reqObj.method(),
        failure: reqObj.failure(),
      }),
    );
    page.on('response', (resp) => {
      const status = resp.status();
      if (status >= 400) logger.warn('page.response', { url: resp.url(), status });
    });

    // Step 4: Set viewport
    const viewportStart = Date.now();
    await page.setViewport({ width: 1200, height: 1200, deviceScaleFactor: 1 });
    timings.viewport = Date.now() - viewportStart;

    // Step 4: Navigate to page
    const gotoStart = Date.now();
    await page.goto(`${baseUrl}/renderer.html?headless=1`, {
      waitUntil: 'domcontentloaded', // Much faster than networkidle0, sufficient for our needs
      timeout: 30000 // 30 seconds timeout
    });
    timings.pageGoto = Date.now() - gotoStart;

    // Set a longer timeout for complex renders
    page.setDefaultTimeout(120000); // 2 minutes for page operations

    // Step 5: Evaluate render
    const evaluateStart = Date.now();
    const result = await page.evaluate(
      async (json, opts) => {
        try {
          const payload = await window.__renderAndGetDataURL(json, opts);
          return { payload, error: null };
        } catch (e) {
          return { payload: null, error: { message: e.message, stack: e.stack } };
        }
      },
      proxiedJson,
      options,
    );
    timings.evaluate = Date.now() - evaluateStart;

    if (result.error) {
      const renderError = new Error(result.error.message);
      renderError.stack = result.error.stack;
      renderError.details = pageErrors;
      throw renderError;
    }

    const payload = result.payload;
    const includesBoundingBoxes = Boolean(options?.showBoundingBoxes);
    const baseNormalized = typeof payload === 'string'
      ? { dataUrl: payload, boundingBoxes: [], dimensions: null }
      : {
          dataUrl: payload?.dataUrl,
          boundingBoxes: Array.isArray(payload?.boundingBoxes) ? payload.boundingBoxes : [],
          dimensions: payload?.dimensions && Number.isFinite(payload.dimensions.width) && Number.isFinite(payload.dimensions.height)
            ? { width: Number(payload.dimensions.width), height: Number(payload.dimensions.height) }
            : null,
        };
    const normalized = {
      ...baseNormalized,
      includesBoundingBoxes,
    };

    if (!normalized.dataUrl) {
      const missing = new Error('Renderer did not return a dataUrl payload');
      missing.details = pageErrors;
      throw missing;
    }

    // Step 6: Log timings
    timings.total = Date.now() - totalStart;
    logger.info('renderLayout.timings', {
      googleFonts: `${timings.googleFonts}ms`,
      transform: `${timings.transform}ms`,
      pageCreate: `${timings.pageCreate}ms`,
      viewport: `${timings.viewport}ms`,
      pageGoto: `${timings.pageGoto}ms`,
      evaluate: `${timings.evaluate}ms`,
      total: `${timings.total}ms`
    });

    return normalized;
  } catch (e) {
    e.details = [...(e.details || []), ...pageErrors].filter((v, i, a) => a.indexOf(v) === i);
    throw e;
  } finally {
    // Clear caches and revoke blob URLs before closing to free memory
    try {
      await page.evaluate(() => window.__clearRenderCaches?.());
    } catch (e) {
      // Ignore cleanup errors (page may already be closed or navigated away)
    }
    const closeStart = Date.now();
    await page.close();
    timings.pageClose = Date.now() - closeStart;
  }
}

async function renderLayouts(browser, baseUrl, layouts, options = {}) {
  const normalizedLayouts = layouts.map(normalizeLayout);
  return Promise.all(normalizedLayouts.map((layout) => renderLayout(browser, baseUrl, layout, options)));
}

function dataUrlToBuffer(renderResult) {
  const dataUrl = typeof renderResult === 'string' ? renderResult : renderResult?.dataUrl || '';
  const [, base64] = dataUrl.split(',');
  return Buffer.from(base64 || '', 'base64');
}

module.exports = {
  injectGoogleFonts,
  transformUrlsToProxy,
  normalizeLayout,
  renderLayout,
  renderLayouts,
  dataUrlToBuffer,
  publicDir: path.resolve(__dirname, '..', 'public'),
};
