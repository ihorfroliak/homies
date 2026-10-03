import createClient, { type Middleware } from "openapi-fetch";

import { ApiError, errorFromResponse } from "./errors";
import type { paths } from "./schema";

/**
 * Browser client: typed from docs/api/openapi.json, always through the BFF
 * (/bff/v1/...), never to the backend origin. Every request carries the CSRF
 * header; the session travels in httpOnly cookies the script cannot read.
 */
export const BFF_BASE = "/bff";

const csrf: Middleware = {
  onRequest({ request }) {
    request.headers.set("x-homies-csrf", "1");
    return request;
  },
};

export function browserClient(fetchImpl: typeof fetch = (input, init) => globalThis.fetch(input, init)) {
  const client = createClient<paths>({ baseUrl: BFF_BASE, credentials: "same-origin", fetch: fetchImpl });
  client.use(csrf);
  return client;
}

/**
 * Unwrap an openapi-fetch result into data or a typed ApiError. Network and
 * abort failures become `network` / `timeout` errors instead of raw TypeErrors.
 */
export async function unwrap<T>(method: string, call: () => Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await call();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    throw new ApiError({ kind: timedOut ? "timeout" : "network" });
  }
  if (result.response.ok && result.data !== undefined) return result.data;
  if (result.response.status === 502 || result.response.status === 504) {
    throw new ApiError({ kind: result.response.status === 504 ? "timeout" : "unavailable", status: result.response.status });
  }
  throw errorFromResponse(method, result.response.status, result.response.headers, result.error);
}
