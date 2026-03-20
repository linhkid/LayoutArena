import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const imageUrl = req.query.url as string;

  if (!imageUrl) {
    return res.status(400).json({ error: 'Image URL is required' });
  }

  try {
    // Fetch the image from the remote server
    const imageResponse = await fetch(imageUrl);

    if (!imageResponse.ok) {
      throw new Error(`Failed to fetch image: ${imageResponse.statusText}`);
    }

    // Get the content type from the original response
    const contentType = imageResponse.headers.get('content-type');
    if (contentType) {
      res.setHeader('Content-Type', contentType);
    }

    // Set CORS headers to allow font loading
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    // Stream the image back to the client
    // The 'readable-stream' package might be needed depending on your Node version.
    // If you have Node.js v18+, you can directly use imageResponse.body.
    const imageBuffer = await imageResponse.arrayBuffer();
    res.send(Buffer.from(imageBuffer));
    
  } catch (error: any) {
    console.error('Image proxy error:', error);
    res.status(500).json({ error: 'Failed to proxy image', details: error.message });
  }
}

/**
 * Scans a JSON template and rewrites absolute http(s) URLs for images and fonts
 * to use the local image proxy. This avoids CORS issues in Puppeteer.
 * @param {object} json The original JSON template object.
 * @returns {object} The transformed JSON object with proxied URLs.
 */
function transformUrlsToProxy(json) {
  // Ensure the expected structure exists
  if (!json?.data?.children || !Array.isArray(json.data.children)) {
    return json;
  }

  const newChildren = json.data.children.map(child => {
    // Create a copy to avoid directly mutating the original object
    const newChild = { ...child };
    const keysToProxy = ['src', 's3FilePath'];

    for (const key of keysToProxy) {
      const url = newChild[key];
      // Check if the value is a string and an absolute URL
      if (typeof url === 'string' && url.startsWith('http')) {
        newChild[key] = `/api/image_proxy?url=${encodeURIComponent(url)}`;
      }
    }
    
    // Also handle the nested URL for SVG elements
    if (newChild.svgElement && typeof newChild.svgElement.svgUrl === 'string' && newChild.svgElement.svgUrl.startsWith('http')) {
      newChild.svgElement = {
        ...newChild.svgElement,
        svgUrl: `/api/image_proxy?url=${encodeURIComponent(newChild.svgElement.svgUrl)}`
      };
    }

    return newChild;
  });

  // Return a new JSON object with the modified children array
  return {
    ...json,
    data: {
      ...json.data,
      children: newChildren,
    },
  };
}