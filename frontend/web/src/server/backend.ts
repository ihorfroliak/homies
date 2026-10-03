import "server-only";

import createClient from "openapi-fetch";

import type { paths } from "@/api/schema";

import { serverEnv } from "./env";

/**
 * Server-side access to the backend. Every call forwards the end user's IP
 * (so the backend rate limiter keys on the person, not on this web server) and
 * the request id (one id from the edge to the database log), and has a
 * deadline. The browser never talks to the backend directly except for
 * /v1/media photos.
 */
export interface CallContext {
  clientIp?: string;
  requestId: string;
  accessToken?: string;
}

export function forwardedHeaders(ctx: CallContext): Headers {
  const headers = new Headers({ accept: "application/json", "x-request-id": ctx.requestId });
  // Overwrite, never append: the backend trusts exactly one hop (this server).
  if (ctx.clientIp) headers.set("x-forwarded-for", ctx.clientIp);
  if (ctx.accessToken) headers.set("authorization", `Bearer ${ctx.accessToken}`);
  return headers;
}

/** Raw call used by the BFF proxy: the path is already validated against the allowlist. */
export async function backendFetch(path: string, init: { method: string; ctx: CallContext; body?: BodyInit | null; contentType?: string | null; signal?: AbortSignal }): Promise<Response> {
  const env = serverEnv();
  const headers = forwardedHeaders(init.ctx);
  if (init.contentType) headers.set("content-type", init.contentType);
  const signal = init.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(env.apiTimeoutMs)]) : AbortSignal.timeout(env.apiTimeoutMs);
  return fetch(`${env.apiInternalUrl}${path}`, {
    method: init.method,
    headers,
    body: init.body ?? null,
    signal,
    cache: "no-store",
    redirect: "manual",
  });
}

/** Typed client for Server Components and route handlers. */
export function backendClient(ctx: CallContext) {
  const env = serverEnv();
  return createClient<paths>({
    baseUrl: env.apiInternalUrl,
    headers: Object.fromEntries(forwardedHeaders(ctx).entries()),
    fetch: (request: Request) => fetch(request, { signal: AbortSignal.any([request.signal, AbortSignal.timeout(env.apiTimeoutMs)]), cache: "no-store" }),
  });
}
