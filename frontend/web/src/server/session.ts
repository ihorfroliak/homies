import "server-only";

/**
 * BFF session: the backend's bearer pair lives only in httpOnly cookies; the
 * browser never sees a token (FE-001 §3).
 *
 *   __Host-hm_at  access token  (Max-Age = expires_in)
 *   __Host-hm_rt  refresh token (Max-Age = 30 days, backend refresh TTL)
 *
 * `__Host-` requires Secure + Path=/ + no Domain. Browsers accept Secure cookies
 * on http://localhost, so the same names work in development.
 *
 * The backend revokes a refresh token the moment it is used and has no grace
 * window, so two concurrent refreshes with the same token log the user out.
 * `refreshOnce` is a per-process single-flight keyed by the token: concurrent
 * callers in this process share one backend call. (Several web replicas would
 * need sticky sessions or a shared lock — recorded as a scaling item.)
 */
export const ACCESS_COOKIE = "__Host-hm_at";
export const REFRESH_COOKIE = "__Host-hm_rt";
export const REFRESH_MAX_AGE_S = 30 * 24 * 3600;

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface CookieWriter {
  set(name: string, value: string, options: CookieOptions): void;
}

export interface CookieOptions {
  httpOnly: true;
  secure: true;
  sameSite: "lax";
  path: "/";
  maxAge: number;
}

function options(maxAge: number): CookieOptions {
  return { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge };
}

export function writeSession(cookies: CookieWriter, pair: TokenPair): void {
  // Expire the access cookie a little early so the BFF refreshes before the
  // backend would refuse (no JWT leeway is added anywhere).
  cookies.set(ACCESS_COOKIE, pair.access_token, options(Math.max(1, pair.expires_in - 30)));
  cookies.set(REFRESH_COOKIE, pair.refresh_token, options(REFRESH_MAX_AGE_S));
}

export function clearSession(cookies: CookieWriter): void {
  cookies.set(ACCESS_COOKIE, "", options(0));
  cookies.set(REFRESH_COOKIE, "", options(0));
}

export type RefreshResult = { ok: true; pair: TokenPair } | { ok: false; reason: "rejected" | "unavailable" };

const inFlight = new Map<string, Promise<RefreshResult>>();

export function refreshOnce(refreshToken: string, call: (token: string) => Promise<RefreshResult>): Promise<RefreshResult> {
  const existing = inFlight.get(refreshToken);
  if (existing) return existing;
  const pending = call(refreshToken).finally(() => {
    // Keep the settled result briefly so a request that read the old cookie a
    // moment later still gets the rotated pair instead of a revoked-token 401.
    setTimeout(() => inFlight.delete(refreshToken), 10_000).unref?.();
  });
  inFlight.set(refreshToken, pending);
  return pending;
}

/** Test hook. */
export function resetRefreshFlights(): void {
  inFlight.clear();
}
