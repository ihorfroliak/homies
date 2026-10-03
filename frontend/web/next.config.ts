import path from "node:path";

import type { NextConfig } from "next";

// The design tokens live next to the app (frontend/design-system/tokens.css) and
// are imported from outside the app directory, so the project root is frontend/.
const frontendRoot = path.join(__dirname, "..");

/**
 * Photos are served by the backend at /v1/media/{id}. In production the edge
 * routes /v1/media/* straight to the backend (keeping the end user's IP for
 * its rate limiter, and never passing this app's cookies along), and the app
 * itself must not proxy them: a production build fails unless MEDIA_VIA_EDGE=1
 * says the edge does it. Local development and the E2E build
 * (HOMIES_WEB_ENV=development) proxy through a rewrite. Rewrites are fixed at
 * build time, so these variables are read at build (SEC-003).
 * docs/frontend/FE-001-foundation.md §5.
 */
const productionBuild = process.env.NODE_ENV === "production" && process.env.HOMIES_WEB_ENV !== "development";
const mediaViaEdge = process.env.MEDIA_VIA_EDGE === "1";
if (productionBuild && !mediaViaEdge) {
  throw new Error("Production build: set MEDIA_VIA_EDGE=1 (the edge routes /v1/media to the backend); the app does not proxy photos in production.");
}
const apiOrigin = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: { root: frontendRoot },
  outputFileTracingRoot: frontendRoot,
  async rewrites() {
    if (mediaViaEdge) return [];
    return [{ source: "/v1/media/:id", destination: `${apiOrigin}/v1/media/:id` }];
  },
};

export default config;
