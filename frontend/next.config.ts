import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  distDir: 'out',
  trailingSlash: true,
  devIndicators: false,
  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
