import { readFileSync } from "node:fs";
import path from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AREA_HUES, areaHue } from "./area-colour";
import { AreaExplorer } from "./area-explorer";

const areas = [
  { id: "1", name: "Kazimierz", slug: "kazimierz" },
  { id: "2", name: "Stare Miasto", slug: "stare-miasto" },
  { id: "3", name: "Bez trasy", slug: null },
];

describe("area hue", () => {
  it("keeps the 001C hues of known districts", () => {
    expect(areaHue("stare-miasto")).toBe(60);
    expect(areaHue("podgorze")).toBe(120);
    expect(areaHue("krowodrza")).toBe(230);
  });

  it("gives any other area a stable hue that has a style rule", () => {
    for (const slug of ["nowa-dzielnica", "x", ""]) {
      expect(AREA_HUES).toContain(areaHue(slug));
      expect(areaHue(slug)).toBe(areaHue(slug));
    }
  });

  it("has exactly one CSS rule per hue, so no tile renders without its colour", () => {
    const css = readFileSync(path.join(__dirname, "area-explorer.module.css"), "utf8");
    const rules = [...css.matchAll(/data-hue="(\d+)"\] \{ --h: (\d+); \}/g)].map((m) => [Number(m[1]), Number(m[2])]);
    for (const [attr, value] of rules) expect(attr).toBe(value);
    expect(rules.map(([h]) => h).sort((a, b) => a! - b!)).toEqual([...AREA_HUES]);
  });
});

describe("AreaExplorer", () => {
  it("links each routable area to its results, skips areas without a slug, and offers the whole city", () => {
    render(<AreaExplorer citySlug="krakow" areas={areas} />);
    const region = screen.getByRole("region", { name: "Kraków po okolicach" });
    expect(within(region).getByRole("link", { name: "Kazimierz" })).toHaveAttribute("href", "/wynajem/krakow/kazimierz");
    expect(within(region).getByRole("link", { name: "Stare Miasto" })).toHaveAttribute("href", "/wynajem/krakow/stare-miasto");
    expect(within(region).queryByText("Bez trasy")).toBeNull();
    expect(within(region).getByRole("link", { name: "Cały Kraków" })).toHaveAttribute("href", "/wynajem/krakow");
  });

  it("says in words that colour means place, names every area, and shows no counts", () => {
    render(<AreaExplorer citySlug="krakow" areas={areas} />);
    const region = screen.getByRole("region", { name: "Kraków po okolicach" });
    expect(within(region).getByText("Kolor oznacza obszar, nie ocenę.")).toBeVisible();
    for (const link of within(region).getAllByRole("link")) expect(link.textContent).not.toMatch(/\d/);
  });

  it("keeps the whole-city route when no area can be loaded", () => {
    render(<AreaExplorer citySlug="krakow" areas={[]} />);
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Cały Kraków" })).toBeVisible();
  });
});
