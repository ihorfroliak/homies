import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HomeSearch } from "./home-search";

describe("HomeSearch", () => {
  it("is a plain GET form to /szukaj with the canonical parameter names", () => {
    render(<HomeSearch cityName="Kraków" areas={[{ id: "1", name: "Kazimierz", slug: "kazimierz" }, { id: "2", name: "Bez trasy", slug: null }]} />);
    const form = screen.getByRole("search", { name: "Wyszukiwarka mieszkań w Krakowie" });
    expect(form).toHaveAttribute("method", "get");
    expect(form).toHaveAttribute("action", "/szukaj");
    expect(screen.getByLabelText("Gdzie")).toHaveAttribute("name", "obszar");
    expect(screen.getByLabelText("Łącznie miesięcznie do (zł)")).toHaveAttribute("name", "koszt_do");
    expect(screen.getByRole("radio", { name: "2+" })).toHaveAttribute("name", "pokoje_od");
  });

  it("offers the whole city first and only areas that have a route", () => {
    render(<HomeSearch cityName="Kraków" areas={[{ id: "1", name: "Kazimierz", slug: "kazimierz" }, { id: "2", name: "Bez trasy", slug: null }]} />);
    const options = screen.getAllByRole("option").map((o) => [o.textContent, o.getAttribute("value")]);
    expect(options).toEqual([["Cały Kraków", ""], ["Kazimierz", "kazimierz"]]);
    expect(screen.getByRole("radio", { name: "Dowolnie" })).toBeChecked();
  });

  it("still searches the whole city without any area", () => {
    render(<HomeSearch cityName="Kraków" areas={[]} />);
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Pokaż mieszkania" })).toBeVisible();
  });
});
