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

  // A malformed percent-escape ("/wynajem/%C0") makes Next.js's own param
  // decoding throw (a 500). It names no page: answer 404 here, with the headers.
  let response: NextResponse;
  try {
    decodeURIComponent(new URL(request.url).pathname);
    response = NextResponse.next({ request: { headers: forwarded } });
  } catch {
    response = new NextResponse("Nie znaleźliśmy tej strony.", { status: 404, headers: { "content-type": "text/plain; charset=utf-8" } });
  }
  response.headers.set("content-security-policy", csp);
  response.headers.set("x-request-id", requestId);
  for (const [name, value] of Object.entries(staticSecurityHeaders(httpsOnly))) response.headers.set(name, value);
  const robots = robotsHeader(process.env.INDEXING_ENABLED === "1", request.nextUrl.pathname);
  if (robots) response.headers.set("x-robots-tag", robots);
  return response;
}

export const config = {
  matcher: [
    // Everything except static build output, the photo passthrough and the map
    // worker files (a module worker takes the CSP of its own response; the
    // page's nonce policy would block the worker's same-origin import).
    // Anchored exclusions: "/v1/media-x" or "/favicon.ico/x" still get the headers.
    { source: "/((?!_next/static/|_next/image$|v1/media/|vendor/|favicon\\.ico$).*)" },
  ],
};
