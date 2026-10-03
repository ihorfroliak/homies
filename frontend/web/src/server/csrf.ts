/**
 * CSRF defence for BFF state-changing requests (cookies are SameSite=Lax, which
 * is not enough on its own). A request is accepted only when ALL hold:
 *   1. Sec-Fetch-Site is "same-origin" (or absent on very old browsers, then
 *      Origin decides);
 *   2. Origin equals the app's public origin;
 *   3. the custom header X-Homies-CSRF: 1 is present — a cross-site form or
 *      simple request cannot set it without a CORS preflight, which the BFF
 *      never grants.
 */
export const CSRF_HEADER = "x-homies-csrf";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export type CsrfVerdict = { ok: true } | { ok: false; reason: "fetch-site" | "origin" | "header" };

export function checkCsrf(method: string, headers: Headers, publicOrigin: string): CsrfVerdict {
  if (SAFE_METHODS.has(method.toUpperCase())) return { ok: true };
  const site = headers.get("sec-fetch-site");
  if (site !== null && site !== "same-origin") return { ok: false, reason: "fetch-site" };
  if (headers.get("origin") !== publicOrigin) return { ok: false, reason: "origin" };
  if (headers.get(CSRF_HEADER) !== "1") return { ok: false, reason: "header" };
  return { ok: true };
}
