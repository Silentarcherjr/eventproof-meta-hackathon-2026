import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // the e2e build uses its own output dir so it never clobbers a running `next dev`
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
