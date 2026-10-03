import "server-only";

import { cookies, headers } from "next/headers";

import { backendFetch, type CallContext } from "./backend";
import { clientIp } from "./client-ip";
import { serverEnv } from "./env";
import { requestIdFrom } from "./request-id";
import { ACCESS_COOKIE, REFRESH_COOKIE, clearSession, refreshOnce, writeSession, type RefreshResult, type TokenPair } from "./session";

/** Call context for the current request: forwarded IP, request id, access token. */
export async function currentContext(): Promise<CallContext & { refreshToken?: string }> {
  const h = await headers();
  const jar = await cookies();
  return {
    clientIp: clientIp(h.get("x-forwarded-for"), undefined, serverEnv().trustProxyHops),
    requestId: requestIdFrom(h),
    accessToken: jar.get(ACCESS_COOKIE)?.value || undefined,
    refreshToken: jar.get(REFRESH_COOKIE)?.value || undefined,
  };
}

async function callRefresh(ctx: CallContext, token: string): Promise<RefreshResult> {
  let response: Response;
  try {
    response = await backendFetch("/v1/auth/refresh", {
      method: "POST",
      ctx: { clientIp: ctx.clientIp, requestId: ctx.requestId },
      body: JSON.stringify({ refresh_token: token }),
      contentType: "application/json",
    });
  } catch {
    return { ok: false, reason: "unavailable" };
  }
  if (response.status === 401) return { ok: false, reason: "rejected" };
  if (!response.ok) return { ok: false, reason: "unavailable" };
  return { ok: true, pair: (await response.json()) as TokenPair };
}

/**
 * Obtain a fresh access token via the refresh cookie (single-flight). Writes the
 * rotated pair to the cookies; clears them when the backend rejects the token.
 * Must run in a route handler or server action (cookie writes).
 */
export async function refreshSession(ctx: CallContext & { refreshToken?: string }): Promise<string | undefined> {
  if (!ctx.refreshToken) return undefined;
  const result = await refreshOnce(ctx.refreshToken, (t) => callRefresh(ctx, t));
  const jar = await cookies();
  if (result.ok) {
    writeSession(jar, result.pair);
    return result.pair.access_token;
  }
  if (result.reason === "rejected") clearSession(jar);
  return undefined;
}

/**
 * Run a backend call with the session: refresh first when only the refresh
 * cookie is left, and once more after a 401 (a 401 means the request was not
 * executed, so repeating it is safe for any method).
 */
export async function withSession(
  ctx: CallContext & { refreshToken?: string },
  auth: "none" | "optional" | "required",
  call: (accessToken: string | undefined) => Promise<Response>,
): Promise<Response> {
  if (auth === "none") return call(undefined);
  let token = ctx.accessToken;
  if (!token && ctx.refreshToken) token = await refreshSession(ctx);
  if (!token && auth === "required") {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }
  const first = await call(token);
  if (first.status !== 401 || !token) return first;
  const renewed = ctx.refreshToken ? await refreshSession({ ...ctx, accessToken: undefined }) : undefined;
  if (renewed) return call(renewed);
  // A dead session must never break a public read: answer it anonymously.
  return auth === "optional" ? call(undefined) : first;
}
