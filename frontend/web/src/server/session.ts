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

/**
 * Rotation memory (SEC-001). The backend revokes the old refresh token the
 * moment it rotates it. If the browser aborts the request that triggered the
 * rotation (a filter count, a closed map card, a navigation), the Set-Cookie
 * with the new pair never arrives and the next call would present a revoked
 * token — a silent logout. So a successful rotation is remembered, keyed by
 * the OLD token, for ROTATION_TTL_MS: a later caller presenting the old token
 * gets the same new pair (and its cookies) instead of a backend refresh.
 *
 * Bounded (MAX_ROTATIONS, oldest evicted first). An `unavailable` outcome is
 * never remembered (the next caller retries). Accepted trade-off: whoever
 * holds the old token within the window obtains the new pair — the same power
 * the old token gave them a moment earlier; recorded in FE-001 §3.
 */
export const ROTATION_TTL_MS = 120_000;
export const MAX_ROTATIONS = 10_000;

const inFlight = new Map<string, Promise<RefreshResult>>();
const rotated = new Map<string, { at: number; result: RefreshResult }>();

function remember(token: string, result: RefreshResult, now: number): void {
  rotated.set(token, { at: now, result });
  while (rotated.size > MAX_ROTATIONS) {
    const oldest = rotated.keys().next().value;
    if (oldest === undefined) break;
    rotated.delete(oldest);
  }
}

export function refreshOnce(refreshToken: string, call: (token: string) => Promise<RefreshResult>, now: () => number = Date.now): Promise<RefreshResult> {
  const known = rotated.get(refreshToken);
  if (known && now() - known.at < ROTATION_TTL_MS) return Promise.resolve(known.result);
  if (known) rotated.delete(refreshToken);
  const existing = inFlight.get(refreshToken);
  if (existing) return existing;
  const pending = call(refreshToken)
    .then((result) => {
      // A rejection is final too (the token is dead): remembering it spares the backend.
      if (result.ok || result.reason === "rejected") remember(refreshToken, result, now());
      return result;
    })
    .finally(() => inFlight.delete(refreshToken));
  inFlight.set(refreshToken, pending);
  return pending;
}

/** Test hook. */
export function resetRefreshFlights(): void {
  inFlight.clear();
  rotated.clear();
}
