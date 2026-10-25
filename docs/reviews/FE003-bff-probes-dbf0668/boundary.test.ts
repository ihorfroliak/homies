import { beforeEach, describe, expect, it, vi } from "vitest";
const m = vi.hoisted(() => ({ fetch: vi.fn(), values: new Map<string,string>(), set: vi.fn() }));
vi.mock("next/headers", () => ({ headers: async () => new Headers({ "x-request-id": "audit-request" }), cookies: async () => ({ get: (k: string) => m.values.has(k) ? { value: m.values.get(k) } : undefined, set: m.set }) }));
vi.mock("@/server/backend", () => ({ backendFetch: m.fetch }));
vi.mock("@/server/env", () => ({ serverEnv: () => ({ publicOrigin: "https://homies.example", trustProxyHops: 0 }) }));
import { POST as register } from "@/app/bff/auth/register/route";
import { GET as session } from "@/app/bff/auth/session/route";
import { GET as proxy } from "@/app/bff/v1/[...path]/route";
import { matchRoute, safeApiPath } from "@/server/bff-routes";
const good = { origin: "https://homies.example", "x-homies-csrf": "1", "sec-fetch-site": "same-origin" };
const credentials = { email: "audit@example.com", password: "fictional-password" };
function req(body: unknown, headers: Record<string,string> = good) { return new Request("https://homies.example/bff/auth/register", { method: "POST", headers, body: JSON.stringify(body) }); }
function prox(path: string[], method = "GET", query = "", headers: Record<string,string> = good, body?: string) { return proxy(new Request(`https://homies.example/bff/v1/${path.join("/")}${query}`, { method, headers, body }), { params: Promise.resolve({ path }) }); }
beforeEach(() => { vi.resetAllMocks(); m.values.clear(); });
describe("independent register negatives", () => {
  it.each([[], null, "text", 12, {}, { email: 1, password: "x" }, { email: "x", password: [] }, { ...credentials, full_name: null }, { ...credentials, full_name: {} }])("rejects invalid shape %j before upstream", async body => { const r = await register(req(body)); expect(r.status).toBe(422); expect(r.headers.get("cache-control")).toBe("no-store"); expect(m.fetch).not.toHaveBeenCalled(); });
  it.each([{ ...good, origin: "null" }, { ...good, origin: "https://homies.example.evil.test" }, { ...good, "sec-fetch-site": "same-site" }, { origin: good.origin }, { "x-homies-csrf": "1" }])("rejects CSRF variant %j", async headers => { expect((await register(req(credentials, headers))).status).toBe(403); expect(m.fetch).not.toHaveBeenCalled(); });
  it("bounds streamed multibyte bytes and declared lengths", async () => {
    for (const r of [req({ ...credentials, full_name: "ą".repeat(2200) }), req(credentials, { ...good, "content-length": "4097" }), req(credentials, { ...good, "content-length": "invalid" })]) expect((await register(r)).status).toBe(413);
    expect(m.fetch).not.toHaveBeenCalled();
  });
  it("strips roles/unknown fields and existing bearer from both calls; writes protected cookies only after login", async () => {
    m.values.set("__Host-hm_at", "old-access");
    m.fetch.mockResolvedValueOnce(Response.json({ id: "new" }, { status: 201 })).mockResolvedValueOnce(Response.json({ access_token: "synthetic-at", refresh_token: "synthetic-rt", expires_in: 1800 }));
    const r = await register(req({ ...credentials, role: "admin", phone: "+48123456789", email_verified_at: "today", __proto__: { role: "host" } }));
    expect(await r.json()).toEqual({ authenticated: true });
    expect(JSON.parse(m.fetch.mock.calls[0][1].body)).toEqual({ ...credentials, full_name: "" });
    expect(JSON.parse(m.fetch.mock.calls[1][1].body)).toEqual(credentials);
    for (const call of m.fetch.mock.calls) expect(call[1].ctx.accessToken).toBeUndefined();
    expect(m.set.mock.calls.map(c => c[0])).toEqual(["__Host-hm_at", "__Host-hm_rt"]);
    for (const c of m.set.mock.calls) expect(c[2]).toMatchObject({ httpOnly: true, secure: true, sameSite: "lax", path: "/" });
  });
  it("does not establish a session when the chained login refuses", async () => {
    m.fetch.mockResolvedValueOnce(Response.json({}, { status: 201 })).mockResolvedValueOnce(Response.json({ detail: "limited" }, { status: 429, headers: { "retry-after": "7", "set-cookie": "unsafe=1", location: "https://evil.test" } }));
    const r = await register(req(credentials)); expect(r.status).toBe(429); expect(r.headers.get("retry-after")).toBe("7"); expect(r.headers.get("set-cookie")).toBeNull(); expect(r.headers.get("location")).toBeNull(); expect(m.set).not.toHaveBeenCalled();
  });
  it("hides thrown upstream details", async () => { m.fetch.mockRejectedValue(new Error("synthetic private internals")); const r = await register(req(credentials)); expect(r.status).toBe(502); expect(await r.text()).not.toContain("private internals"); expect(m.set).not.toHaveBeenCalled(); });
});
describe("independent session minimization", () => {
  it.each([null, undefined, "2026-10-01T10:00:00Z"])("uses verification timestamp only (%s), drops contact/role", async stamp => {
    m.values.set("__Host-hm_at", "synthetic-at"); m.fetch.mockResolvedValue(Response.json({ id: "u", full_name: "Fictional User", email: "private@example.com", phone: "+48123456789", role: "host", email_verified_at: null, phone_verified_at: stamp }));
    const r = await session(); expect(await r.json()).toEqual({ authenticated: true, user: { id: "u", name: "Fictional User", emailVerified: false, phoneVerified: Boolean(stamp) } }); expect(r.headers.get("cache-control")).toBe("no-store");
  });
  it("does not fetch anonymous session", async () => { expect(await (await session()).json()).toEqual({ authenticated: false }); expect(m.fetch).not.toHaveBeenCalled(); });
});
describe("independent proxy boundary", () => {
  const privateRoutes: [string,string][] = [["GET","me/saved-listings"],["POST","me/saved-listings/a"],["DELETE","me/saved-listings/a"],["GET","me/saved-searches"],["POST","me/saved-searches"],["GET","me/saved-searches/a"],["GET","me/saved-searches/a/matches"],["PATCH","me/saved-searches/a"],["DELETE","me/saved-searches/a"],["GET","me/viewings"],["GET","me/classifieds"],["GET","me/reveal-quota"],["GET","conversations"],["GET","conversations/a"],["POST","conversations/a/messages"],["POST","classifieds/a/conversations"],["POST","classifieds/a/viewings"],["POST","classifieds/a/contact"],["GET","classifieds/a/viewings"],["POST","viewings/a/confirm"],["POST","viewings/a/decline"],["POST","viewings/a/cancel"],["POST","viewings/a/outcome"],["POST","reports"],["POST","me/verify/phone/start"],["POST","me/verify/phone/confirm"]];
  it.each(privateRoutes)("requires caller credentials for %s %s", async (method,path) => { expect(matchRoute(method, `/v1/${path}`)?.auth).toBe("required"); const r = await prox(path.split("/"), method); expect(r.status).toBe(401); expect(r.headers.get("cache-control")).toBe("no-store"); expect(m.fetch).not.toHaveBeenCalled(); });
  it.each(["admin/users","me/roles","auth/login","auth/register","conversations/a/messages/b","classifieds/a/viewing-settings","classifieds/a/viewing-windows","me/saved-searches/a/delete","me/saved-searches/a/extra"])("rejects nonallowlisted %s", async path => { expect((await prox(path.split("/")))).toHaveProperty("status",404); expect(m.fetch).not.toHaveBeenCalled(); });
  it.each(["..",".","a/b","a\\b","a%2fb","a%252fb","a?x","a#x",""])("rejects path separator/dot %s", part => { expect(safeApiPath(["v1", part])).toBeUndefined(); });
  it("keeps query in the query portion and drops unapproved response headers", async () => {
    m.values.set("__Host-hm_at", "synthetic-at"); m.fetch.mockResolvedValue(Response.json({ items: [] }, { headers: { "set-cookie": "bad=1", "cache-control": "public,max-age=3600", "access-control-allow-origin": "*" } }));
    const r = await prox(["me","saved-searches"],"GET","?limit=5&path=%2Fv1%2Fadmin&x=%23fragment");
    expect(m.fetch.mock.calls[0][0]).toBe("/v1/me/saved-searches?limit=5&path=%2Fv1%2Fadmin&x=%23fragment"); expect(r.headers.get("cache-control")).toBe("no-store"); expect(r.headers.get("set-cookie")).toBeNull(); expect(r.headers.get("access-control-allow-origin")).toBeNull();
  });
  it.each(["/v1/me/saved-searches/abc-123","https://evil.test/v1/me/saved-searches/a","//evil.test/x","/v1/admin/a","/v1/me/saved-searches/../admin","/v1/me/saved-searches/a?x=1","/v1/me/saved-searches/a%2fb"])("limits Location %s", async location => {
    m.values.set("__Host-hm_at", "synthetic-at"); m.fetch.mockResolvedValue(Response.json({ detail: "duplicate" }, { status: 409, headers: { location } })); const r = await prox(["me","saved-searches"],"POST"); expect(r.headers.get("location")).toBe(location === "/v1/me/saved-searches/abc-123" ? location : null);
  });
  it("applies CSRF and stream size before authenticated writes", async () => {
    m.values.set("__Host-hm_at", "synthetic-at"); expect((await prox(["reports"],"POST","",{})).status).toBe(403); expect((await prox(["reports"],"POST","",good,"x".repeat(65537))).status).toBe(413); expect(m.fetch).not.toHaveBeenCalled();
  });
});
