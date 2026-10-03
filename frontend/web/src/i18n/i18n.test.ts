import { describe, expect, it } from "vitest";

import { formatCalendarDate, formatInstant, formatMoney, plural, t } from ".";

// Intl uses narrow no-break spaces in pl-PL; compare on normalised spaces.
const norm = (s: string) => s.replace(/[  ]/g, " ");

describe("Polish formatting", () => {
  it("groups four-digit prices and drops zero decimals", () => {
    expect(norm(formatMoney(345_000))).toBe("3 450 zł");
    expect(norm(formatMoney(1_234_567_00))).toBe("1 234 567 zł");
    expect(norm(formatMoney(345_050))).toBe("3 450,50 zł");
    expect(norm(formatMoney(0))).toBe("0 zł");
  });

  it("refuses non-integer minor units", () => {
    expect(() => formatMoney(10.5)).toThrow(TypeError);
  });

  it("uses all Polish plural categories", () => {
    expect(norm(plural(t.plural.listings, 1))).toBe("1 oferta");
    expect(norm(plural(t.plural.listings, 3))).toBe("3 oferty");
    expect(norm(plural(t.plural.listings, 5))).toBe("5 ofert");
    expect(norm(plural(t.plural.listings, 22))).toBe("22 oferty");
    expect(norm(plural(t.plural.listings, 1240))).toBe("1 240 ofert");
    expect(norm(plural(t.plural.rooms, 2))).toBe("2 pokoje");
  });

  it("keeps calendar dates on their day and instants in Europe/Warsaw", () => {
    expect(formatCalendarDate("2026-11-01")).toMatch(/^1 lis 2026/);
    // 23:30 UTC on 31 Dec is already 1 Jan in Warsaw (winter, UTC+1).
    expect(formatInstant("2026-12-31T23:30:00Z")).toMatch(/1 sty 2027.*00:30/);
    expect(() => formatCalendarDate("2026-11-01T00:00:00Z")).toThrow(RangeError);
  });

  it("never uses the forbidden wording", () => {
    const all = JSON.stringify(t).toLowerCase();
    expect(all).not.toContain("zweryfikowan");
    expect(all).not.toContain("wygasł");
    expect(all).not.toMatch(/!"/);
  });
});
