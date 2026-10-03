import { describe, expect, it } from "vitest";

import { domainCode, errorFromResponse, invalidParams, retryAfter } from "./errors";

const none = new Headers();

describe("errorFromResponse", () => {
  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
    [422, "validation"],
    [429, "rate_limited"],
    [500, "server"],
  ])("maps %i to %s", (status, kind) => {
    expect(errorFromResponse("GET", status, none, { detail: "x" }).kind).toBe(kind);
  });

  it("treats a 503 on a write as an unknown outcome, never retryable", () => {
    const write = errorFromResponse("POST", 503, new Headers({ "retry-after": "5" }), { detail: "The database stopped answering…" });
    expect(write.kind).toBe("outcome_unknown");
    expect(write.retryable).toBe(false);
    const put = errorFromResponse("PUT", 503, none, {});
    expect(put.kind).toBe("outcome_unknown");
    const read = errorFromResponse("GET", 503, new Headers({ "retry-after": "5" }), {});
    expect(read.kind).toBe("unavailable");
    expect(read.retryable).toBe(true);
    expect(read.retryAfterSeconds).toBe(5);
  });

  it("extracts stable domain codes and the request id", () => {
    const e = errorFromResponse("POST", 409, new Headers({ "x-request-id": "req-12345678" }), { detail: "RECONTACT_BLOCKED: Homies closed your conversation" });
    expect(e.code).toBe("RECONTACT_BLOCKED");
    expect(e.requestId).toBe("req-12345678");
  });
});

describe("helpers", () => {
  it("reads domain codes only from a leading CODE: prefix", () => {
    expect(domainCode("CONVERSATION_CLOSED: closed")).toBe("CONVERSATION_CLOSED");
    expect(domainCode("Invalid credentials")).toBeUndefined();
    expect(domainCode([{ loc: ["query", "x"] }])).toBeUndefined();
  });

  it("parses Retry-After seconds and dates, bounded", () => {
    expect(retryAfter("12")).toBe(12);
    expect(retryAfter("999999")).toBe(3600);
    expect(retryAfter(null)).toBeUndefined();
    expect(retryAfter("nonsense")).toBeUndefined();
    expect(retryAfter(new Date(Date.now() + 10_000).toUTCString())).toBeGreaterThanOrEqual(9);
  });

  it("lists the parameters a 422 refused", () => {
    expect(invalidParams({ detail: [{ loc: ["query", "min_rooms"] }, { loc: ["query", "sort"] }, { loc: ["path", "id"] }] })).toEqual(["min_rooms", "sort"]);
    expect(invalidParams({ detail: "x" })).toEqual([]);
  });
});
