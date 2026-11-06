import { beforeEach, describe, expect, it } from "vitest";

import { readResults, rememberResults, safeResultsPath } from "./last-results";

describe("last results path", () => {
  beforeEach(() => sessionStorage.clear());

  it("keeps filters and view of a results path", () => {
    rememberResults("/wynajem/krakow?koszt_do=5000&widok=mapa");
    expect(readResults()).toBe("/wynajem/krakow?koszt_do=5000&widok=mapa");
  });

  it("refuses anything that is not a same-origin results path", () => {
    for (const bad of ["https://example.com/wynajem", "//example.com/wynajem", "/wynajem//example.com", "/wynajemx", "/oferta/1", "/wynajem\\..", null, 7, `/wynajem?${"a".repeat(2100)}`]) {
      expect(safeResultsPath(bad), String(bad)).toBeUndefined();
    }
    sessionStorage.setItem("homies.search.last-results", "https://example.com/wynajem");
    expect(readResults()).toBeUndefined();
  });

  it("accepts the bare and nested results routes", () => {
    for (const good of ["/wynajem", "/wynajem/krakow", "/wynajem?pokoje_od=2", "/wynajem/krakow/kazimierz?sort=najtansze"]) {
      expect(safeResultsPath(good)).toBe(good);
    }
  });
});
