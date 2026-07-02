import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained .next/standalone server for a lean Docker image
  // (see apps/web/Dockerfile). No effect on `next dev`.
  output: "standalone",
};

export default nextConfig;
