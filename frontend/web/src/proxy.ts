import { NextResponse, type NextRequest } from "next/server";

import { requestIdFrom } from "@/server/request-id";
import { contentSecurityPolicy, originsOf, robotsHeader, staticSecurityHeaders } from "@/server/security-headers";

/**
 * Next.js 16 request proxy (formerly middleware): one request id per request,
 * a fresh CSP nonce, security headers, and the noindex kill switch.
 * Pages that use the nonce are rendered dynamically (Next.js requirement).
 */
export function proxy(request: NextRequest): NextResponse {
  const development = process.env.NODE_ENV !== "production";
  // A local production build (E2E) runs on http://localhost: no HTTPS upgrade there.
  const httpsOnly = !development && process.env.HOMIES_WEB_ENV !== "development";
  const nonce = btoa(crypto.randomUUID());
  const requestId = requestIdFrom(request.headers);
  const csp = contentSecurityPolicy({
    nonce,
    development,
    httpsOnly,
    mapOrigins: originsOf([process.env.NEXT_PUBLIC_MAP_STYLE_URL, ...(process.env.MAP_EXTRA_ORIGINS ?? "").split(",")]),
  });

  const forwarded = new Headers(request.headers);
  forwarded.set("x-nonce", nonce);
  forwarded.set("x-request-id", requestId);
  forwarded.set("content-security-policy", csp);

  const response = NextResponse.next({ request: { headers: forwarded } });
  response.headers.set("content-security-policy", csp);
  response.headers.set("x-request-id", requestId);
  for (const [name, value] of Object.entries(staticSecurityHeaders(httpsOnly))) response.headers.set(name, value);
  const robots = robotsHeader(process.env.INDEXING_ENABLED === "1", request.nextUrl.pathname);
  if (robots) response.headers.set("x-robots-tag", robots);
  return response;
}

export const config = {
  matcher: [
    // Everything except static build output and the photo passthrough.
    { source: "/((?!_next/static|_next/image|v1/media|favicon.ico).*)" },
  ],
};
