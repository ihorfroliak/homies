import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/errors";
import { api, retrySend } from "./api";
import { INTENT_TTL, safeIntent } from "./intent";
import { errorCopy } from "./copy";
describe("intent minimisation", () => {
  const base = { action: "message", listing_id: "abc-123", initiator_id: "open-message", created_at: 1000 };
  it("drops sensitive and unknown fields even when supplied in storage", () => expect(safeIntent({ ...base, body: "private", phone: "+48123456789", role: "host", note: "private", password: "secret" }, 2000)).toEqual(base));
  it("expires and refuses future and malformed intent timestamps", () => { expect(safeIntent(base, 1000 + INTENT_TTL)).toBeUndefined(); expect(safeIntent(base, 999)).toBeUndefined(); });
  it("refuses unsafe ids and free-text search parameters", () => { expect(safeIntent({ ...base, listing_id: "../admin" }, 2000)).toBeUndefined(); expect(safeIntent({ ...base, action: "save_search", search_query: "q=private" }, 2000)).toBeUndefined(); });
  it("preserves only safe canonical search parameters", () => expect(safeIntent({ ...base, action: "save_search", search_query: "country_code=PL&max_rent=300000" }, 2000)?.search_query).toBe("country_code=PL&max_rent=300000"));
});
describe("operation-specific response policy", () => {
  it("accepts204 without parsing a body", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 }))); await expect(api("/v1/me/saved-listings/abc", "DELETE")).resolves.toBeUndefined(); vi.unstubAllGlobals(); });
  it.each([401, 429, 500, 502, 503, 504])("retains keyed sends for transient%s", status => expect(retrySend(new ApiError({ status, kind: status === 503 ? "outcome_unknown" : "server" }))).toBe(true));
  it("ends keyed sends on final domain refusals", () => { expect(retrySend(new ApiError({ status: 429, kind: "rate_limited", code: "CONVERSATION_QUOTA" }))).toBe(false); expect(retrySend(new ApiError({ status: 409, kind: "conflict", code: "RECONTACT_BLOCKED" }))).toBe(false); });
  it("never presents backend prose", () => expect(errorCopy(new ApiError({ kind: "server", message: "sensitive backend detail" }))).not.toContain("sensitive"));
});
