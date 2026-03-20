import { logger, getRequestContext } from '../../../lib/logger';
import { renderLayouts } from '../../../lib/renderHelpers';
import { getPool } from '../../../lib/browserPool';

export const config = { 
  api: { 
    bodyParser: { sizeLimit: '5mb' },
    responseLimit: '50mb'
  },
  maxDuration: 300 // 5 minutes (max for Vercel Pro, use 60 for Hobby)
};

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  let json;
  try {
    json = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
  } catch {
    logger.error('api.render.preview.parseJson', new Error('Invalid JSON'), {
      req: getRequestContext(req),
      bodyType: typeof req.body,
    });
    return res.status(400).json({ error: 'Invalid JSON', message: 'The request body could not be parsed as JSON.' });
  }

  const isBatch = Array.isArray(json);
  const layouts = isBatch ? json : [json];
  const {
    showBoundingBoxes: showBoundingBoxesQuery,
    downloadBoundingBoxes,
    format: requestedFormat,
    download,
  } = req.query;
  const isTruthy = (value) => value === 'true' || value === '1' || value === true;
  const shouldDownloadBoundingBoxes = isTruthy(downloadBoundingBoxes);
  const shouldShowBoundingBoxes = shouldDownloadBoundingBoxes || isTruthy(showBoundingBoxesQuery);
  const format = shouldDownloadBoundingBoxes ? 'png' : requestedFormat;
  const forceDownload = isTruthy(download);
  const renderOptions = { showBoundingBoxes: shouldShowBoundingBoxes };

  const browserPool = getPool({
    maxInstances: 3,
    idleTimeout: 60000, // Close idle browsers after 1 minute
  });

  let browser;
  try {
    browser = await browserPool.getBrowser();

    const baseUrl = `http://${req.headers.host}`;
    const results = await renderLayouts(browser, baseUrl, layouts, renderOptions);

    if (isBatch) {
      if (format === 'png') {
        return res.status(400).json({
          error: 'Unsupported format for batch render',
          message: 'Batch rendering to PNG is not supported. Request individual renders when using format=png.',
        });
      }
      const responseItems = results.map((item) => ({
        dataUrl: item.dataUrl,
        boundingBoxes: item.boundingBoxes,
        dimensions: item.dimensions,
        includesBoundingBoxes: item.includesBoundingBoxes,
      }));

      return res.status(200).json({
        dataUrls: responseItems.map((item) => item.dataUrl),
        boundingBoxesList: responseItems.map((item) => item.boundingBoxes),
        dimensionsList: responseItems.map((item) => item.dimensions),
        renders: responseItems,
      });
    } else {
      const renderResult = results[0];
      if (!renderResult) {
        throw new Error('Render did not produce an output');
      }

      const dataUrl = renderResult.dataUrl;
      if (format === 'png') {
        const b64 = dataUrl.split(',')[1] || '';
        const buf = Buffer.from(b64, 'base64');
        res.setHeader('Content-Type', 'image/png');
        if (forceDownload || shouldDownloadBoundingBoxes) {
          const fileName = renderOptions.showBoundingBoxes ? 'render_with_bounding_boxes.png' : 'render.png';
          res.setHeader('Content-Disposition', `attachment; filename="${fileName}"`);
        }
        res.setHeader('Content-Length', buf.length);
        return res.status(200).send(buf);
      }
      return res.status(200).json({
        dataUrl,
        boundingBoxes: renderResult.boundingBoxes,
        dimensions: renderResult.dimensions,
        includesBoundingBoxes: renderResult.includesBoundingBoxes,
        render: renderResult,
      });
    }
  } catch (e) {
    logger.error('api.render.preview', e, { req: getRequestContext(req) });
    return res.status(500).json({
      error: 'Render failed',
      message: e.message || 'An unknown error occurred during rendering.',
      details: e.details || []
    });
  } finally {
    if (browser) {
      // Release browser back to pool instead of closing
      browserPool.releaseBrowser(browser);
    }
  }
}
