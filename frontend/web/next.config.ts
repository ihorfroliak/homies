import path from "node:path";

import type { NextConfig } from "next";

// The design tokens live next to the app (frontend/design-system/tokens.css) and
// are imported from outside the app directory, so the project root is frontend/.
const frontendRoot = path.join(__dirname, "..");

const apiOrigin = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: { root: frontendRoot },
  outputFileTracingRoot: frontendRoot,
  async rewrites() {
    // Local development only: photos are served by the backend at /v1/media/{id}.
    // In production the edge proxy routes /v1/media/* straight to the backend
    // (keeping the end user's IP for the rate limiter); MEDIA_VIA_EDGE=1 turns
    // this rewrite off. docs/frontend/FE-001-foundation.md §5.
    if (process.env.MEDIA_VIA_EDGE === "1") return [];
    return [{ source: "/v1/media/:id", destination: `${apiOrigin}/v1/media/:id` }];
  },
};

export default config;
