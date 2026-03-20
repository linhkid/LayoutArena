import { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';
import { lookup } from 'mime-types';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { path: imagePath } = req.query;

  if (!imagePath || typeof imagePath !== 'string') {
    return res.status(400).json({ error: 'Image path is required' });
  }

  try {
    // Security: Validate that the path exists and is accessible
    if (!fs.existsSync(imagePath)) {
      return res.status(404).json({ error: 'Image not found', path: imagePath });
    }

    // Security: Ensure it's a file, not a directory
    const stats = fs.statSync(imagePath);
    if (!stats.isFile()) {
      return res.status(400).json({ error: 'Path is not a file' });
    }

    // Read the image file
    const imageBuffer = fs.readFileSync(imagePath);

    // Detect MIME type from file extension
    const mimeType = lookup(imagePath) || 'application/octet-stream';

    // Set appropriate headers
    res.setHeader('Content-Type', mimeType);
    res.setHeader('Content-Length', imageBuffer.length);
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');

    // Send the image
    res.send(imageBuffer);

  } catch (error: any) {
    console.error('Local image serving error:', error);
    res.status(500).json({
      error: 'Failed to serve local image',
      details: error.message,
      path: imagePath
    });
  }
}

/**
 * Helper function to convert absolute file paths to proxy URLs
 * Usage: const proxyUrl = getLocalImageProxyUrl('/var/folders/.../image.png')
 * @param {string} absolutePath The absolute file system path
 * @returns {string} The proxy URL that can be used in the browser
 */
export function getLocalImageProxyUrl(absolutePath: string): string {
  if (!absolutePath || typeof absolutePath !== 'string') {
    return absolutePath;
  }

  // If it's already a URL, return as-is
  if (absolutePath.startsWith('http://') ||
      absolutePath.startsWith('https://') ||
      absolutePath.startsWith('data:')) {
    return absolutePath;
  }

  // Convert absolute path to proxy URL
  return `/api/local_image?path=${encodeURIComponent(absolutePath)}`;
}

/**
 * Transform JSON template to use local image proxy for absolute file paths
 * @param {object} json The original JSON template object
 * @returns {object} The transformed JSON with proxied local paths
 */
export function transformLocalPathsToProxy(json: any): any {
  if (!json?.data?.children || !Array.isArray(json.data.children)) {
    return json;
  }

  const newChildren = json.data.children.map((child: any) => {
    const newChild = { ...child };
    const keysToProxy = ['src', 's3FilePath'];

    for (const key of keysToProxy) {
      const value = newChild[key];
      // Check if it's an absolute file path
      if (typeof value === 'string' &&
          (value.startsWith('/') || value.startsWith('/Users/') ||
           value.startsWith('/var/') || value.startsWith('/home/'))) {
        newChild[key] = getLocalImageProxyUrl(value);
      }
    }

    // Handle nested SVG element URLs
    if (newChild.svgElement?.svgUrl) {
      const svgUrl = newChild.svgElement.svgUrl;
      if (typeof svgUrl === 'string' &&
          (svgUrl.startsWith('/') || svgUrl.startsWith('/Users/') ||
           svgUrl.startsWith('/var/') || svgUrl.startsWith('/home/'))) {
        newChild.svgElement = {
          ...newChild.svgElement,
          svgUrl: getLocalImageProxyUrl(svgUrl)
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
