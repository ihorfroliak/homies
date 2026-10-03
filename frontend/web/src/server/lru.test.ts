import { describe, expect, it } from "vitest";

import { TtlLru } from "./lru";
import { readCapped } from "./body";

describe("TtlLru", () => {
  it("is bounded, evicts the least recently used, and expires", () => {
    let now = 0;
    const c = new TtlLru<number>(2, 100, () => now);
    c.set("a", 1);
    c.set("b", 2);
    expect(c.get("a")?.value).toBe(1); // a is now most recent
    c.set("c", 3);
    expect(c.get("b")).toBeUndefined();
    expect(c.size).toBe(2);
    now = 150;
    expect(c.get("a")).toBeUndefined();
  });

  it("caches null results too (a slug that names nothing)", () => {
    const c = new TtlLru<string | null>(10, 1000);
    c.set("x", null);
    expect(c.get("x")).toEqual({ value: null });
  });
});

describe("readCapped", () => {
  it("refuses a declared or streamed body over the cap", async () => {
    const big = new Request("http://x/", { method: "POST", body: "x".repeat(10), headers: { "content-length": "10" } });
    expect(await readCapped(big, 5)).toBeNull();
    const ok = await readCapped(new Request("http://x/", { method: "POST", body: "hello" }), 5);
    expect(new TextDecoder().decode(ok!)).toBe("hello");
    const stream = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode("abc")); c.enqueue(new TextEncoder().encode("def")); c.close(); } });
    const chunked = new Request("http://x/", { method: "POST", body: stream, duplex: "half" } as RequestInit);
    expect(await readCapped(chunked, 5)).toBeNull();
  });
});
