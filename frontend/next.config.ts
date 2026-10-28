import type { NextConfig } from "next";

// Container build (frontend/Dockerfile): the browser talks to the studio origin only, and /api/* is proxied to
// the backend. Both values are read at build time.
const apiProxyTarget = process.env.API_PROXY_TARGET;

const nextConfig: NextConfig = {
  // the e2e build uses its own output dir so it never clobbers a running `next dev`
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // a live run, or a 3-round Muse repair, can take minutes; the default proxy timeout is 30 s
  experimental: { proxyTimeout: 300_000 },
  async rewrites() {
    return apiProxyTarget ? [{ source: "/api/:path*", destination: `${apiProxyTarget.replace(/\/$/, "")}/:path*` }] : [];
  },
};

export default nextConfig;
