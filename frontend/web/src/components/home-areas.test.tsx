import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { HomeAreas } from "./home-areas";

afterEach(cleanup);

it("does not generate broken routes for reference rows without a public slug", () => {
  render(<HomeAreas areas={[{ id: "area-1", name: "Unnamed route", slug: null }]} />);
  expect(screen.queryByText("Unnamed route")).not.toBeInTheDocument();
  expect(screen.getAllByRole("link")).toHaveLength(1);
  expect(screen.getByRole("link")).toHaveAttribute("href", "/wynajem/krakow");
});

it("links the actual public area slug without substituting a hard-coded district", () => {
  render(<HomeAreas areas={[{ id: "area-1", name: "Nowa Huta", slug: "nowa-huta" }]} />);
  expect(screen.getByRole("link", { name: "Nowa Huta" })).toHaveAttribute("href", "/wynajem/krakow/nowa-huta");
  expect(screen.queryByText(/Kazimierz/)).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zobacz cały Kraków" })).toHaveAttribute("href", "/wynajem/krakow");
});

it("keeps city search available when reference data is missing, without inventing areas or prices", () => {
  render(<HomeAreas areas={[]} />);
  expect(screen.getByRole("status")).toHaveTextContent("Nie udało się wczytać okolic");
  expect(screen.getAllByRole("link")).toHaveLength(1);
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/zł|\d+ ofert/);
});

it("announces loading separately from an unavailable reference response", () => {
  render(<HomeAreas areas={[]} loading />);
  expect(screen.getByRole("region")).toHaveAttribute("aria-busy", "true");
  expect(screen.getByRole("status")).toHaveTextContent("Ładowanie");
  expect(screen.queryByText(/Nie udało/)).not.toBeInTheDocument();
});

it("escapes public names and contains unusual slugs in a single path segment", () => {
  render(<HomeAreas areas={[{ id: "area-1", name: "<script>alert(1)</script>", slug: "area?next=/konto" }]} />);
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByRole("link", { name: "<script>alert(1)</script>" })).toHaveAttribute("href", "/wynajem/krakow/area%3Fnext%3D%2Fkonto");
});
