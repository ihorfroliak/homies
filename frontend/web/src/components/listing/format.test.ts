import { describe, expect, it } from "vitest";

import { coverOf, factsLine, freshnessLabel, monthlyLabel, moveInLabel, placeLabel } from "./format";

const norm = (s: string | undefined) => s?.replace(/[  ]/g, " ");

describe("listing formatting", () => {
  it("marks the monthly total by how honest it is about utilities", () => {
    expect(norm(monthlyLabel({ monthly_total_estimate: 345_000, utilities_basis: "INCLUDED" }))).toBe("3 450 zł / mies.");
    expect(norm(monthlyLabel({ monthly_total_estimate: 345_000, utilities_basis: "ESTIMATED" }))).toBe("ok. 3 450 zł / mies.");
    expect(norm(monthlyLabel({ monthly_total_estimate: 345_000, utilities_basis: "NOT_STATED" }))).toBe("od 3 450 zł / mies.");
  });

  it("never reads a missing move-in date as available now", () => {
    expect(moveInLabel({ move_in: "UNKNOWN", available_from: null })).toBe("Termin nie podany");
    expect(moveInLabel({ move_in: "NOW", available_from: "2026-01-01" })).toBe("Od zaraz");
    expect(moveInLabel({ move_in: "FROM_DATE", available_from: "2026-11-01" })).toMatch(/^Od 1 lis 2026/);
  });

  it("says 'confirmed current', never 'verified', and hides stale", () => {
    expect(freshnessLabel({ freshness: "FRESH", confirmed_on: "2026-10-03" })).toMatch(/^Potwierdzona jako aktualna 3 paź 2026/);
    expect(freshnessLabel({ freshness: "STALE", confirmed_on: "2026-10-03" })).toBeUndefined();
    expect(freshnessLabel({ freshness: null, confirmed_on: null })).toBeUndefined();
  });

  it("picks the cover, else the first photo", () => {
    const a = { id: "a", is_cover: false, url: "/a", media_type: "PHOTO" };
    const b = { id: "b", is_cover: true, url: "/b", media_type: "PHOTO" };
    expect(coverOf({ media: [a, b] })?.id).toBe("b");
    expect(coverOf({ media: [a] })?.id).toBe("a");
    expect(coverOf({ media: [] })).toBeUndefined();
  });

  it("shows place and facts that exist, nothing invented", () => {
    expect(placeLabel({ city: "Kraków", district: "Kazimierz" })).toBe("Kazimierz, Kraków");
    expect(placeLabel({ city: "Kraków", district: "" })).toBe("Kraków");
    const facts = { rooms: 2, area_m2: 48, has_elevator: false, furnished: "full", parking: "none", pets_allowed: false };
    expect(factsLine({ space_type: "WHOLE_PROPERTY", facts })).toEqual(["2 pok.", "48 m²"]);
    expect(factsLine({ space_type: "ROOM", facts: { ...facts, space_area_m2: 14.4 } })).toEqual(["Pokój", "2 pok.", "14 m²"]);
    expect(factsLine({ space_type: "WHOLE_PROPERTY", facts: null })).toEqual([]);
  });
});
