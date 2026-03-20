/**** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Disable image optimization for data URLs
  images: { unoptimized: true },
  // Increase API response size limit
  experimental: {
    isrMemoryCacheSize: 0,
  },
  // If deploying to Vercel, these settings will help with large responses
  api: {
    responseLimit: '50mb',
  },
};

module.exports = nextConfig;
