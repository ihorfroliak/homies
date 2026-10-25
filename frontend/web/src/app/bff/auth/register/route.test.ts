import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ fetch: vi.fn(), write: vi.fn(), jar: {} }));
vi.mock("next/headers", () => ({ cookies: async () => mocks.jar }));
vi.mock("@/server/backend", () => ({ backendFetch: mocks.fetch }));
vi.mock("@/server/bff", () => ({ currentContext: async () => ({ requestId: "test-request", clientIp: "127.0.0.1" }) }));
vi.mock("@/server/env", () => ({ serverEnv: () => ({ publicOrigin: "https://homies.example" }) }));
vi.mock("@/server/session", () => ({ writeSession: mocks.write }));
import { POST } from "./route";
function request(body: unknown, headers = { origin: "https://homies.example", "x-homies-csrf": "1" }) { return new Request("https://homies.example/bff/auth/register", { method: "POST", headers, body: JSON.stringify(body) }); }
beforeEach(() => { vi.clearAllMocks(); });
describe("register BFF", () => {
  it("registers then logs in, strips role and keeps tokens in cookies only", async () => {
    mocks.fetch.mockResolvedValueOnce(Response.json({ id: "u" }, { status: 201 })).mockResolvedValueOnce(Response.json({ access_token: "synthetic-access", refresh_token: "synthetic-refresh" }));
    const response = await POST(request({ email: "user@example.com", password: "synthetic-password", full_name: "Anna Nowak", role: "host" }));
    expect(JSON.parse(mocks.fetch.mock.calls[0]![1].body)).toEqual({ email: "user@example.com", password: "synthetic-password", full_name: "Anna Nowak" });
    expect(mocks.fetch.mock.calls.map(call => call[0])).toEqual(["/v1/auth/register", "/v1/auth/login"]);
    expect(mocks.write).toHaveBeenCalledOnce(); expect(await response.json()).toEqual({ authenticated: true }); expect(response.headers.get("cache-control")).toBe("no-store");
  });
  it("refuses cross-site submissions before any upstream call", async () => { expect((await POST(request({}, { origin: "https://evil.example", "x-homies-csrf": "1" }))).status).toBe(403); expect(mocks.fetch).not.toHaveBeenCalled(); });
  it("caps body and rejects null", async () => { expect((await POST(request({ email: "x".repeat(5000) }))).status).toBe(413); expect((await POST(request(null))).status).toBe(422); expect(mocks.fetch).not.toHaveBeenCalled(); });
  it("does not log in after duplicate registration and retains retry-after", async () => { mocks.fetch.mockResolvedValueOnce(Response.json({ detail: "exists" }, { status: 409, headers: { "retry-after": "5" } })); const response = await POST(request({ email: "u@example.com", password: "synthetic-password" })); expect(response.status).toBe(409); expect(mocks.fetch).toHaveBeenCalledOnce(); expect(mocks.write).not.toHaveBeenCalled(); expect(response.headers.get("retry-after")).toBe("5"); });
});
