import { describe, expect, it, vi } from "vitest";

import { BFF_ROUTES, matchRoute, safeApiPath } from "./bff-routes";
import { clientIp } from "./client-ip";
import { checkCsrf } from "./csrf";
import { readServerEnv } from "./env";
import { requestIdFrom } from "./request-id";
import { contentSecurityPolicy, robotsHeader, staticSecurityHeaders } from "./security-headers";
import { refreshOnce, resetRefreshFlights, writeSession, clearSession, ACCESS_COOKIE, REFRESH_COOKIE, type CookieOptions } from "./session";

const ORIGIN = "https://homies.example";

function h(entries: Record<string, string>): Headers {
  return new Headers(entries);
}

describe("csrf", () => {
  const good = { "sec-fetch-site": "same-origin", origin: ORIGIN, "x-homies-csrf": "1" };

  it("lets reads through without checks", () => {
    expect(checkCsrf("GET", h({}), ORIGIN)).toEqual({ ok: true });
  });

  it("accepts a same-origin write with the header", () => {
    expect(checkCsrf("POST", h(good), ORIGIN)).toEqual({ ok: true });
  });

  it.each([
    ["cross-site fetch", { ...good, "sec-fetch-site": "cross-site" }, "fetch-site"],
    ["same-site sibling", { ...good, "sec-fetch-site": "same-site" }, "fetch-site"],
    ["foreign origin", { ...good, origin: "https://evil.example" }, "origin"],
    ["missing origin", { "sec-fetch-site": "same-origin", "x-homies-csrf": "1" }, "origin"],
    ["missing header", { "sec-fetch-site": "same-origin", origin: ORIGIN }, "header"],
  ])("refuses %s", (_name, headers, reason) => {
    expect(checkCsrf("DELETE", h(headers), ORIGIN)).toEqual({ ok: false, reason });
  });

  it("falls back to Origin when Sec-Fetch-Site is absent", () => {
    expect(checkCsrf("POST", h({ origin: ORIGIN, "x-homies-csrf": "1" }), ORIGIN)).toEqual({ ok: true });
  });
});

describe("clientIp", () => {
  it("ignores X-Forwarded-For with zero trusted hops", () => {
    expect(clientIp("1.2.3.4", undefined, 0)).toBeUndefined();
    expect(clientIp("1.2.3.4", "10.0.0.9", 0)).toBe("10.0.0.9");
  });

  it("takes the address the trusted ingress appended", () => {
    expect(clientIp("6.6.6.6, 203.0.113.7", undefined, 1)).toBe("203.0.113.7");
    expect(clientIp("6.6.6.6, 203.0.113.7, 10.0.0.2", undefined, 2)).toBe("203.0.113.7");
  });

  it("refuses short chains and garbage", () => {
    expect(clientIp("203.0.113.7", undefined, 2)).toBeUndefined();
    expect(clientIp("not-an-ip", undefined, 1)).toBeUndefined();
    expect(clientIp("999.1.1.1", undefined, 1)).toBeUndefined();
    expect(clientIp("2001:db8::1", undefined, 1)).toBe("2001:db8::1");
  });
});

describe("requestId", () => {
  it("keeps a sane caller id and replaces anything else", () => {
    expect(requestIdFrom(h({ "x-request-id": "abc12345-xyz" }))).toBe("abc12345-xyz");
    expect(requestIdFrom(h({ "x-request-id": "short" }))).not.toBe("short");
    expect(requestIdFrom(h({ "x-request-id": "a".repeat(65) }))).toHaveLength(36);
    expect(requestIdFrom(h({ "x-request-id": "bad id with spaces" }))).toHaveLength(36);
  });
});

describe("env", () => {
  it("has local defaults outside production", () => {
    const env = readServerEnv({ NODE_ENV: "development" });
    expect(env.apiInternalUrl).toBe("http://127.0.0.1:8000");
    expect(env.indexingEnabled).toBe(false);
  });

  it("fails closed in production", () => {
    expect(() => readServerEnv({ NODE_ENV: "production" })).toThrow(/API_INTERNAL_URL/);
    expect(() => readServerEnv({ NODE_ENV: "production", API_INTERNAL_URL: "http://api:8000" })).toThrow(/PUBLIC_ORIGIN/);
    expect(() => readServerEnv({ NODE_ENV: "production", API_INTERNAL_URL: "http://api:8000", PUBLIC_ORIGIN: "http://homies.pl", TRUST_PROXY_HOPS: "1" })).toThrow(/https/);
    expect(() => readServerEnv({ NODE_ENV: "production", API_INTERNAL_URL: "http://api:8000", PUBLIC_ORIGIN: "https://homies.pl" })).toThrow(/TRUST_PROXY_HOPS/);
    expect(() => readServerEnv({ NODE_ENV: "production", API_INTERNAL_URL: "http://api:8000", PUBLIC_ORIGIN: "https://homies.pl", TRUST_PROXY_HOPS: "-1" })).toThrow();
  });

  it("accepts a complete production configuration", () => {
    const env = readServerEnv({ NODE_ENV: "production", API_INTERNAL_URL: "http://api:8000/", PUBLIC_ORIGIN: "https://homies.pl/", TRUST_PROXY_HOPS: "1", INDEXING_ENABLED: "1" });
    expect(env).toMatchObject({ production: true, apiInternalUrl: "http://api:8000", publicOrigin: "https://homies.pl", trustProxyHops: 1, indexingEnabled: true });
  });
});

describe("bff routes", () => {
  it("allows only listed method + path shapes", () => {
    expect(matchRoute("GET", "/v1/classifieds")).toBeDefined();
    expect(matchRoute("get", "/v1/classifieds/abc-123")).toBeDefined();
    expect(matchRoute("POST", "/v1/classifieds")).toBeUndefined();
    expect(matchRoute("GET", "/v1/admin/moderation/queue")).toBeUndefined();
    expect(matchRoute("GET", "/v1/me")?.auth).toBe("required");
  });

  it("never proxies admin routes", () => {
    for (const route of BFF_ROUTES) expect(route.pattern.source).not.toContain("admin");
  });

  it("rejects dot segments and smuggled separators", () => {
    expect(safeApiPath(["v1", "classifieds"])).toBe("/v1/classifieds");
    expect(safeApiPath(["v1", "..", "admin"])).toBeUndefined();
    expect(safeApiPath(["v1", "a/b"])).toBeUndefined();
    expect(safeApiPath(["v1", "a%2fb"])).toBeUndefined();
    expect(safeApiPath(["v2", "x"])).toBeUndefined();
    expect(safeApiPath([])).toBeUndefined();
  });
});

describe("session cookies", () => {
  function jar() {
    const set = new Map<string, { value: string; options: CookieOptions }>();
    return { set: (name: string, value: string, options: CookieOptions) => set.set(name, { value, options }), store: set };
  }

  it("writes both tokens as __Host- httpOnly cookies and expires the access cookie early", () => {
    const j = jar();
    writeSession(j, { access_token: "a", refresh_token: "r", expires_in: 1800 });
    expect(j.store.get(ACCESS_COOKIE)).toEqual({ value: "a", options: { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 1770 } });
    expect(j.store.get(REFRESH_COOKIE)?.options.maxAge).toBe(30 * 24 * 3600);
    clearSession(j);
    expect(j.store.get(ACCESS_COOKIE)?.options.maxAge).toBe(0);
    expect(j.store.get(REFRESH_COOKIE)?.value).toBe("");
  });

  it("single-flights concurrent refreshes of one token (backend revokes on use)", async () => {
    resetRefreshFlights();
    const call = vi.fn(async () => ({ ok: true as const, pair: { access_token: "a2", refresh_token: "r2", expires_in: 1800 } }));
    const results = await Promise.all([refreshOnce("r1", call), refreshOnce("r1", call), refreshOnce("r1", call)]);
    expect(call).toHaveBeenCalledTimes(1);
    expect(new Set(results.map((r) => (r.ok ? r.pair.access_token : "")))).toEqual(new Set(["a2"]));
    await refreshOnce("other", call);
    expect(call).toHaveBeenCalledTimes(2);
  });
});

describe("security headers", () => {
  it("builds a nonce CSP with no third-party script origin", () => {
    const csp = contentSecurityPolicy({ nonce: "n0nce", development: false, httpsOnly: true, mapOrigins: [] });
    expect(csp).toContain("script-src 'self' 'nonce-n0nce' 'strict-dynamic'");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).not.toMatch(/https?:\/\//);
  });

  it("lists configured map origins only for images and connections", () => {
    const csp = contentSecurityPolicy({ nonce: "n", development: false, httpsOnly: true, mapOrigins: ["https://tiles.example"] });
    expect(csp).toMatch(/img-src [^;]*https:\/\/tiles\.example/);
    expect(csp).toMatch(/connect-src [^;]*https:\/\/tiles\.example/);
    expect(csp).not.toMatch(/script-src [^;]*tiles/);
  });

  it("adds HSTS only in production", () => {
    expect(staticSecurityHeaders(false)["strict-transport-security"]).toBeUndefined();
    expect(staticSecurityHeaders(true)["strict-transport-security"]).toContain("max-age=");
  });

  it("noindexes everything while the kill switch is off", () => {
    expect(robotsHeader(false, "/")).toBe("noindex, nofollow");
    expect(robotsHeader(true, "/")).toBeUndefined();
    expect(robotsHeader(true, "/bff/v1/me")).toBe("noindex, nofollow");
  });
});
