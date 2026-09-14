import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  experimental: {
    // The compiler API is reliable across the Node versions used by local and CI builds.
    useTypeScriptCli: false,
  },
  typescript: {
    // Allows an isolated compile after `tsc --noEmit` on runtimes where Next's
    // type-check worker is incompatible (currently Node 26).
    ignoreBuildErrors: process.env.NEXT_SKIP_TYPECHECK === "1",
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "r2.thesportsdb.com" },
      { protocol: "https", hostname: "www.thesportsdb.com" },
      { protocol: "https", hostname: "img.a.transfermarkt.technology" },
    ],
  },
};

export default nextConfig;
