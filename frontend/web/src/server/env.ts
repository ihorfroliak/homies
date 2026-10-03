import "server-only";

/**
 * Server-side configuration, read once per process. Fail closed: in
 * production a missing backend URL or public origin is a startup error, never a
 * silent default (mirrors the backend's fail-closed ENV, PR-001R).
 */
export interface ServerEnv {
  production: boolean;
  /** Backend origin reachable from the web server (never exposed to browsers). */
  apiInternalUrl: string;
  /** The public origin of this web app, e.g. https://homies.pl. Used for CSRF and canonical URLs. */
  publicOrigin: string;
  /** Reverse proxies in front of the web server; 0 = trust the socket only. */
  trustProxyHops: number;
  /** Search-engine indexing. Off unless explicitly enabled (DESIGN-001 §8). */
  indexingEnabled: boolean;
  /** Backend call timeout. */
  apiTimeoutMs: number;
}

function intFrom(raw: string | undefined, fallback: number, name: string): number {
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) throw new Error(`${name} must be a non-negative integer`);
  return value;
}

export function readServerEnv(source: Record<string, string | undefined> = process.env): ServerEnv {
  const production = source.NODE_ENV === "production" && source.HOMIES_WEB_ENV !== "development";
  const apiInternalUrl = source.API_INTERNAL_URL ?? (production ? undefined : "http://127.0.0.1:8000");
  const publicOrigin = source.PUBLIC_ORIGIN ?? (production ? undefined : "http://localhost:3000");
  if (!apiInternalUrl) throw new Error("API_INTERNAL_URL is required in production");
  if (!publicOrigin) throw new Error("PUBLIC_ORIGIN is required in production");
  const origin = new URL(publicOrigin);
  if (production && origin.protocol !== "https:") throw new Error("PUBLIC_ORIGIN must be https in production");
  const trustProxyHops = intFrom(source.TRUST_PROXY_HOPS, 0, "TRUST_PROXY_HOPS");
  // Next.js route handlers cannot read the socket address, so without a trusted
  // ingress hop every user would share the web server's rate-limit bucket.
  if (production && trustProxyHops < 1) throw new Error("TRUST_PROXY_HOPS must be >= 1 in production (behind the ingress)");
  return {
    production,
    apiInternalUrl: apiInternalUrl.replace(/\/+$/, ""),
    publicOrigin: origin.origin,
    trustProxyHops,
    indexingEnabled: source.INDEXING_ENABLED === "1",
    apiTimeoutMs: intFrom(source.API_TIMEOUT_MS, 8000, "API_TIMEOUT_MS"),
  };
}

let cached: ServerEnv | undefined;

export function serverEnv(): ServerEnv {
  cached ??= readServerEnv();
  return cached;
}
