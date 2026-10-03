/**
 * One error model for every backend call (DESIGN-001 §5 state tables).
 *
 * The backend answers FastAPI `{"detail": ...}` bodies. Domain refusals carry a
 * stable code as a prefix of a string detail ("CONVERSATION_CLOSED: ..."); 422
 * carries Pydantic's list. 429 and 503 carry Retry-After.
 *
 * A 503 on a non-idempotent request is classified `outcome_unknown`: the
 * backend's commit_unknown answer has no stable code yet (API gap G10), and any
 * 503 on a write may have committed, so the UI must tell the user to check
 * before repeating — never auto-retry a write.
 */
export type ApiErrorKind =
  | "network"
  | "timeout"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limited"
  | "unavailable"
  | "outcome_unknown"
  | "server";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | undefined;
  /** Stable domain code when the backend gave one, e.g. "RECONTACT_BLOCKED". */
  readonly code: string | undefined;
  readonly retryAfterSeconds: number | undefined;
  readonly requestId: string | undefined;
  /** For a 422: the query/body parameters the backend refused. */
  readonly invalid: string[];

  constructor(init: {
    kind: ApiErrorKind;
    status?: number;
    code?: string;
    retryAfterSeconds?: number;
    requestId?: string;
    invalid?: string[];
    message?: string;
  }) {
    super(init.message ?? init.kind);
    this.name = "ApiError";
    this.kind = init.kind;
    this.status = init.status;
    this.code = init.code;
    this.retryAfterSeconds = init.retryAfterSeconds;
    this.requestId = init.requestId;
    this.invalid = init.invalid ?? [];
  }

  /** Whether repeating the same request automatically is safe. */
  get retryable(): boolean {
    return this.kind === "network" || this.kind === "timeout" || this.kind === "rate_limited" || this.kind === "unavailable";
  }
}

const CODE_PREFIX = /^([A-Z][A-Z0-9_]{2,63}):\s/;
// Only reads: a backend PUT/DELETE may still have side effects (versions, events).
const IDEMPOTENT = new Set(["GET", "HEAD", "OPTIONS"]);

export function domainCode(detail: unknown): string | undefined {
  if (typeof detail !== "string") return undefined;
  return CODE_PREFIX.exec(detail)?.[1];
}

export function retryAfter(value: string | null): number | undefined {
  if (value === null) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.min(Math.ceil(seconds), 3600);
  const date = Date.parse(value);
  if (Number.isNaN(date)) return undefined;
  return Math.min(Math.max(0, Math.ceil((date - Date.now()) / 1000)), 3600);
}

export function errorFromResponse(method: string, status: number, headers: Headers, body: unknown): ApiError {
  const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : undefined;
  const base = {
    status,
    code: domainCode(detail),
    requestId: headers.get("x-request-id") ?? undefined,
    retryAfterSeconds: retryAfter(headers.get("retry-after")),
    invalid: invalidParams(body),
    message: typeof detail === "string" ? detail : `HTTP ${status}`,
  };
  if (status === 401) return new ApiError({ kind: "unauthorized", ...base });
  if (status === 403) return new ApiError({ kind: "forbidden", ...base });
  if (status === 404 || status === 410) return new ApiError({ kind: "not_found", ...base });
  if (status === 409) return new ApiError({ kind: "conflict", ...base });
  if (status === 400 || status === 422) return new ApiError({ kind: "validation", ...base });
  if (status === 429) return new ApiError({ kind: "rate_limited", ...base });
  if (status === 503) {
    const kind = IDEMPOTENT.has(method.toUpperCase()) ? "unavailable" : "outcome_unknown";
    return new ApiError({ kind, ...base });
  }
  return new ApiError({ kind: "server", ...base });
}

/** Pydantic 422 entries reduced to the query/body parameter names that failed. */
export function invalidParams(body: unknown): string[] {
  if (!body || typeof body !== "object" || !("detail" in body)) return [];
  const detail = (body as { detail: unknown }).detail;
  if (!Array.isArray(detail)) return [];
  const names = new Set<string>();
  for (const entry of detail) {
    const loc = (entry as { loc?: unknown }).loc;
    if (Array.isArray(loc) && loc.length >= 2 && (loc[0] === "query" || loc[0] === "body")) {
      names.add(String(loc[loc.length - 1]));
    }
  }
  return [...names];
}
