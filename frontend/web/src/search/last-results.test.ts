import { beforeEach, describe, expect, it } from "vitest";

import { canonicalOrigin, originFor, recordOrigin, safeReturnPath } from "./last-results";

const KEY = "homies.search.listing-origin";

describe("safeReturnPath", () => {
  it("accepts canonical results paths with their filters, sort, view and page", () => {
    for (const good of [
      "/wynajem",
      "/wynajem/krakow",
      "/wynajem/krakow/kazimierz",
      "/wynajem/krakow?koszt_do=5000",
      "/wynajem/krakow?koszt_do=5000&sort=najtansze&widok=mapa",
      "/wynajem/krakow/kazimierz?pokoje_od=2&strona=2",
      "/zapisane",
    ]) {
      expect(safeReturnPath(good), good).toBe(good);
    }
  });

  it.each([
    ["absolute URL", "https://example.com/wynajem"],
    ["absolute URL with results path", "https://example.com/wynajem/krakow"],
    ["protocol-relative", "//example.com/wynajem"],
    ["protocol-relative after the prefix", "/wynajem//example.com"],
    ["javascript scheme", "javascript:alert(1)"],
    ["data scheme", "data:text/html,x"],
    ["encoded slash", "/wynajem/%2f%2fexample.com"],
    ["encoded slash, upper case", "/wynajem/%2F%2Fexample.com"],
    ["double-encoded slash", "/wynajem/%252f%252fexample.com"],
    ["backslash", "/wynajem\\..\\oferta"],
    ["backslash host", "/\\example.com/wynajem"],
    ["encoded backslash", "/wynajem/%5c%5cexample.com"],
    ["double-encoded backslash", "/wynajem/%255cexample.com"],
    ["dot segments", "/wynajem/../oferta/1"],
    ["dot segment in place of a slug", "/wynajem/./krakow"],
    ["encoded dot segments", "/wynajem/%2e%2e/oferta/1"],
    ["mixed encoded dot segments", "/wynajem/.%2e/.%2e/oferta/1"],
    ["fullwidth solidus", "/wynajem/／example.com"],
    ["fullwidth full stop", "/wynajem/．．/oferta"],
    ["non-ASCII slug", "/wynajem/kraków"],
    ["right-to-left mark", "/wynajem/krakow‏"],
    ["tab inside the path", "/wynajem/\t/example.com"],
    ["newline inside the path", "/wynajem/krakow\n"],
    ["too many segments", "/wynajem/a/b/c"],
    ["upper-case slug is not canonical", "/wynajem/Krakow"],
    ["prefix of another route", "/wynajemx"],
    ["unsupported internal route", "/wiadomosci"],
    ["unsupported internal route with results text", "/oferta/wynajem"],
    ["saved with a query", "/zapisane?x=1"],
    ["fragment", "/wynajem/krakow#x"],
    ["unknown query parameter", "/wynajem/krakow?redirect=https://example.com"],
    ["next-style parameter", "/wynajem/krakow?next=//example.com"],
    ["invalid filter value", "/wynajem/krakow?koszt_do=abc"],
    ["non-canonical parameter order", "/wynajem/krakow?widok=mapa&koszt_do=5000"],
    ["empty query", "/wynajem/krakow?"],
    ["too long", `/wynajem/krakow?koszt_do=5000${"&koszt_do=1".repeat(300)}`],
  ])("refuses %s", (_name, bad) => {
    expect(safeReturnPath(bad)).toBeUndefined();
  });

  it("refuses values that are not strings", () => {
    for (const bad of [null, undefined, 7, {}, ["/wynajem"]]) expect(safeReturnPath(bad)).toBeUndefined();
  });
});

describe("canonicalOrigin", () => {
  it("reduces the current location to its canonical results URL", () => {
    expect(canonicalOrigin("/wynajem/krakow", "?widok=mapa&koszt_do=5000")).toBe("/wynajem/krakow?koszt_do=5000&widok=mapa");
    expect(canonicalOrigin("/wynajem/krakow", "?nieznany=1&pokoje_od=abc")).toBe("/wynajem/krakow");
    expect(canonicalOrigin("/zapisane", "")).toBe("/zapisane");
    expect(canonicalOrigin("/zapisane", "?wyszukiwanie=1#wyszukiwania")).toBe("/zapisane");
  });

  it("gives no origin for pages that are not a search or the saved list", () => {
    for (const path of ["/", "/oferta/1", "/wiadomosci/1", "/ogladania", "/wynajem/a/b/c", "/wynajem/%C0"]) {
      expect(canonicalOrigin(path, ""), path).toBeUndefined();
    }
  });
});

describe("listing origin", () => {
  beforeEach(() => sessionStorage.clear());

  it("returns the search a listing was opened from", () => {
    recordOrigin("listing-a", "/wynajem/krakow?koszt_do=5000&widok=mapa");
    expect(originFor("listing-a")).toEqual({ path: "/wynajem/krakow?koszt_do=5000&widok=mapa", kind: "results" });
  });

  it("never offers that search for another listing", () => {
    recordOrigin("listing-a", "/wynajem/warszawa");
    expect(originFor("listing-b")).toBeUndefined();
  });

  it("names the saved list as its own kind of origin", () => {
    recordOrigin("listing-a", "/zapisane");
    expect(originFor("listing-a")).toEqual({ path: "/zapisane", kind: "saved" });
  });

  it("forgets an earlier search when the listing is opened from elsewhere", () => {
    recordOrigin("listing-a", "/wynajem/warszawa");
    recordOrigin("listing-a", undefined);
    expect(originFor("listing-a")).toBeUndefined();
  });

  it("treats storage as untrusted", () => {
    for (const stored of [
      "not json",
      "null",
      "[]",
      "/wynajem/krakow",
      JSON.stringify({ listing: "listing-a" }),
      JSON.stringify({ listing: "listing-a", path: "https://example.com/wynajem" }),
      JSON.stringify({ listing: "listing-a", path: "/wynajem/%2f%2fexample.com" }),
      JSON.stringify({ listing: "listing-a", path: "/wiadomosci" }),
      JSON.stringify({ listing: 7, path: "/wynajem/krakow" }),
    ]) {
      sessionStorage.setItem(KEY, stored);
      expect(originFor("listing-a"), stored).toBeUndefined();
    }
  });
});
