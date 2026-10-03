/**
 * Response security policy, applied by proxy.ts to every page and BFF answer.
 *
 * CSP uses a per-request nonce with 'strict-dynamic' (Next.js reads the nonce
 * from the request's CSP header and stamps its own scripts). No third-party
 * script origin is allowed: there is no vendor SDK (G-12). Map tiles: the
 * development style (G-11) is listed only when MAP_STYLE_URL is configured.
 */
export interface PolicyOptions {
  nonce: string;
  /** Development tooling (React dev needs eval and the HMR socket). */
  development: boolean;
  /** Served over HTTPS only: upgrade-insecure-requests + HSTS. */
  httpsOnly: boolean;
  mapOrigins: readonly string[];
}

export function contentSecurityPolicy({ nonce, development, httpsOnly, mapOrigins }: PolicyOptions): string {
  const map = mapOrigins.join(" ");
  const directives: Record<string, string> = {
    "default-src": "'self'",
    // 'unsafe-eval' only in development: React's dev tooling needs it.
    "script-src": `'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    // Next.js injects style tags for CSS Modules in development; production
    // styles are files. Inline style attributes stay allowed (React `style`).
    "style-src": `'self' 'unsafe-inline'`,
    "img-src": `'self' data: blob:${map ? ` ${map}` : ""}`,
    "font-src": "'self'",
    "connect-src": `'self'${map ? ` ${map}` : ""}${development ? " ws:" : ""}`,
    "worker-src": "'self' blob:", // maplibre-gl workers
    "frame-src": "'none'",
    "frame-ancestors": "'none'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
  };
  const parts = Object.entries(directives).map(([k, v]) => `${k} ${v}`);
  if (httpsOnly) parts.push("upgrade-insecure-requests");
  return parts.join("; ");
}

export function staticSecurityHeaders(httpsOnly: boolean): Record<string, string> {
  const headers: Record<string, string> = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
    "cross-origin-opener-policy": "same-origin",
    "x-frame-options": "DENY",
  };
  if (httpsOnly) headers["strict-transport-security"] = "max-age=31536000; includeSubDomains";
  return headers;
}

/** Search-engine kill switch (DESIGN-001 §8): everything is noindex unless indexing is enabled. */
export function robotsHeader(indexingEnabled: boolean, pathname: string): string | undefined {
  if (!indexingEnabled) return "noindex, nofollow";
  if (pathname.startsWith("/bff/") || pathname.startsWith("/konto") || pathname.startsWith("/panel")) return "noindex, nofollow";
  return undefined; // pages decide with their own robots metadata
}

export function originsOf(urls: readonly (string | undefined)[]): string[] {
  const out = new Set<string>();
  for (const u of urls) {
    if (!u) continue;
    try {
      out.add(new URL(u).origin);
    } catch {
      // ignore malformed configuration; the map then fails closed to no tiles
    }
  }
  return [...out];
}
