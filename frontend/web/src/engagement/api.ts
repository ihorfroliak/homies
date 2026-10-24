import { ApiError, errorFromResponse } from "@/api/errors";
import type { components } from "@/api/schema";
import { trackApiError } from "./analytics";
export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];
export type Listing = Schema<"ClassifiedOut">;
export type Conversation = Schema<"ConversationOut"> | Schema<"ProviderConversationOut">;
export type Viewing = Schema<"ViewingOut"> | Schema<"ProviderViewingOut">;
export class EngagementError extends ApiError { location?: string }
/** Empty204 is success; only stable codes and safe references leave this layer. */
export async function api<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/bff${path}`, { method, credentials: "same-origin", cache: "no-store", signal,
      headers: { "x-homies-csrf": "1", ...(body === undefined ? {} : { "content-type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const failure = new ApiError({ kind: error instanceof DOMException && error.name === "TimeoutError" ? "timeout" : "network" });
    trackApiError(path, failure); throw failure;
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (response.ok) return data as T;
  const error = errorFromResponse(method, response.status, response.headers, data);
  const result = new EngagementError({ kind: error.kind, status: error.status, code: error.code, retryAfterSeconds: error.retryAfterSeconds, invalid: error.invalid });
  const location = response.headers.get("location");
  if (location && /^\/v1\/me\/saved-searches\/[A-Za-z0-9-]{1,64}$/.test(location)) result.location = location.split("/").at(-1);
  trackApiError(path, result); throw result;
}
export function uncertain(error: unknown): boolean { return error instanceof ApiError && (["network", "timeout", "unavailable", "outcome_unknown"].includes(error.kind) || (error.status ?? 0) >= 500); }
export function retrySend(error: unknown): boolean { return uncertain(error) || error instanceof ApiError && (error.status === 401 || error.status === 429 && !error.code); }
