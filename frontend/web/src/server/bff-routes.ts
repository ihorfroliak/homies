/**
 * The BFF proxy allowlist. The browser reaches the backend only through
 * /bff/v1/... and only for these method + path shapes; everything else is 404
 * at the BFF. Admin/moderator routes are never proxied (separate app, canon 03).
 *
 * FE-001 opens the public read surface and the caller's own account; each later
 * slice adds its routes here deliberately (FE-003: saves, conversations,
 * viewings).
 */
export interface BffRoute {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  pattern: RegExp;
  /** Whether the backend route needs the caller's bearer token. */
  auth: "none" | "optional" | "required";
}

const ID = "[A-Za-z0-9-]{1,64}";

export const BFF_ROUTES: readonly BffRoute[] = [
  { method: "GET", pattern: /^\/v1\/classifieds$/, auth: "optional" },
  { method: "GET", pattern: /^\/v1\/classifieds\/map$/, auth: "optional" },
  { method: "GET", pattern: new RegExp(`^/v1/classifieds/${ID}$`), auth: "optional" },
  { method: "GET", pattern: new RegExp(`^/v1/classifieds/${ID}/viewing-slots$`), auth: "optional" },
  { method: "GET", pattern: /^\/v1\/geo\/(countries|localities|areas)$/, auth: "none" },
  { method: "GET", pattern: new RegExp(`^/v1/geo/localities/${ID}/areas$`), auth: "none" },
  { method: "GET", pattern: /^\/v1\/attributes$/, auth: "none" },
  { method: "GET", pattern: /^\/v1\/me$/, auth: "required" },
  { method: "GET", pattern: /^\/v1\/me\/verification$/, auth: "required" },
];

export function matchRoute(method: string, path: string): BffRoute | undefined {
  const m = method.toUpperCase();
  return BFF_ROUTES.find((r) => r.method === m && r.pattern.test(path));
}

/** Query strings pass through, but a path must be a plain /v1 path (no dot segments, no encoded slashes). */
export function safeApiPath(segments: readonly string[]): string | undefined {
  if (segments.length === 0 || segments[0] !== "v1") return undefined;
  for (const s of segments) {
    if (s === "" || s === "." || s === ".." || /[/\\%?#]/.test(s)) return undefined;
  }
  return `/${segments.join("/")}`;
}
