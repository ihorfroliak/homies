import { describe, expect, it } from "vitest";

import { activeFilters, apiQuery, changed, isBare, MAX_PAGE, parseSearch, searchHref } from "./codec";

const p = (q: string) => new URLSearchParams(q);

describe("parseSearch", () => {
  it("reads place, filters, sort, page and view", () => {
    const { state, dropped, badPath } = parseSearch(["krakow", "kazimierz"], p("koszt_do=4000&pokoje_od=2&umeblowanie=czesciowe&parking=garaz&zwierzeta=tak&winda=tak&dostepne_do=2026-12-01&okres_do=12&sort=najtansze&strona=3&widok=mapa"));
    expect(badPath).toBe(false);
    expect(dropped).toEqual([]);
    expect(state).toEqual({
      city: "krakow", area: "kazimierz", monthlyMax: 4000, roomsMin: 2, furnished: "partial", parking: "garage",
      pets: true, elevator: true, availableBy: "2026-12-01", termMax: 12, sort: "price_asc", page: 3, view: "map",
    });
  });

  it("drops invalid, unknown and repeated parameters but keeps searching", () => {
    const { state, dropped } = parseSearch([], p("koszt_do=abc&pokoje_od=0&dostepne_do=2026-02-30&sort=random&strona=0&foo=1&koszt_od=100&koszt_od=200&utm_source=x"));
    expect(dropped.sort()).toEqual(["dostepne_do", "foo", "koszt_do", "koszt_od", "pokoje_od", "sort", "strona"].sort());
    expect(state).toEqual({ monthlyMin: 100, sort: "newest", page: 1, view: "list" });
  });

  it("drops both ends of an inverted range", () => {
    const { state, dropped } = parseSearch([], p("koszt_od=5000&koszt_do=3000"));
    expect(state.monthlyMin).toBeUndefined();
    expect(state.monthlyMax).toBeUndefined();
    expect(dropped).toEqual(["koszt_od", "koszt_do"]);
  });

  it("flags paths that are not city/area slugs", () => {
    expect(parseSearch(["a", "b", "c"], p("")).badPath).toBe(true);
    expect(parseSearch(["Kraków"], p("")).badPath).toBe(true);
    expect(parseSearch(["krakow--x"], p("")).badPath).toBe(true);
    expect(parseSearch(["KRAKOW"], p("")).state.city).toBe("krakow");
    expect(parseSearch(["%C0"], p("")).badPath).toBe(true);
    expect(parseSearch(["a".repeat(121)], p("")).badPath).toBe(true);
    expect(parseSearch(["a".repeat(120)], p("")).badPath).toBe(false);
  });

  it("caps the page at the backend offset limit", () => {
    expect(parseSearch([], p(`strona=${MAX_PAGE}`)).state.page).toBe(MAX_PAGE);
    expect(parseSearch([], p(`strona=${MAX_PAGE + 1}`)).dropped).toEqual(["strona"]);
  });

  it("validates the map box", () => {
    expect(parseSearch([], p("mapa=19.9,50.0,20.0,50.1")).state.bbox).toEqual([19.9, 50, 20, 50.1]);
    for (const bad of ["1,2,3", "20,50,19,51", "a,b,c,d", "19.9,50,20,95"]) expect(parseSearch([], p(`mapa=${bad}`)).dropped).toEqual(["mapa"]);
  });
});

describe("searchHref", () => {
  it("is canonical: fixed order, defaults omitted, round-trips", () => {
    const href = "/wynajem/krakow?koszt_do=4000&pokoje_od=2&winda=tak&sort=najtansze&strona=2";
    const { state } = parseSearch(["krakow"], p("strona=2&sort=najtansze&winda=tak&pokoje_od=2&koszt_do=4000"));
    expect(searchHref(state)).toBe(href);
    const [path, q] = href.split("?");
    expect(searchHref(parseSearch(path!.split("/").slice(2), p(q!)).state)).toBe(href);
    expect(searchHref({ sort: "newest", page: 1, view: "list" })).toBe("/wynajem");
  });

  it("never writes an area without a city", () => {
    expect(searchHref({ area: "kazimierz", sort: "newest", page: 1, view: "list" })).toBe("/wynajem");
  });
});

describe("changes and API mapping", () => {
  it("resets the page on any change and removes cleared filters", () => {
    const s = parseSearch(["krakow"], p("koszt_do=4000&strona=4")).state;
    const next = changed(s, { monthlyMax: undefined });
    expect(next.page).toBe(1);
    expect("monthlyMax" in next).toBe(false);
    expect(changed(s, { page: 5 }).page).toBe(5);
  });

  it("maps whole złoty to minor units and Polish codes to API values", () => {
    const { state } = parseSearch([], p("koszt_od=1500&koszt_do=4000&na_start_do=9000&umeblowanie=brak&sort=najwieksze&mapa=19.9,50,20,50.1"));
    expect(apiQuery(state, { localityId: "L1", areaId: "A1" })).toEqual({
      country_code: "PL", locality_id: ["L1"], geo_area_id: ["A1"], min_monthly_total: 150000, max_monthly_total: 400000,
      max_move_in_total: 900000, furnished: "none", bbox: "19.9,50,20,50.1", sort: "size_desc",
    });
  });

  it("knows what is bare (indexable) and which filters are active", () => {
    expect(isBare(parseSearch(["krakow"], p("")).state)).toBe(true);
    expect(isBare(parseSearch(["krakow"], p("sort=najtansze")).state)).toBe(false);
    expect(isBare(parseSearch(["krakow"], p("widok=mapa")).state)).toBe(false);
    expect(activeFilters(parseSearch([], p("winda=tak&koszt_do=1")).state)).toEqual(["monthlyMax", "elevator"]);
  });
});
