import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";
import { renderToString } from "react-dom/server";

import { HomeDistrictMap } from "./home-district-map";

afterEach(cleanup);

it("preserves district title text in server HTML before hydration", () => {
  const html = renderToString(<HomeDistrictMap />);
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const titles = [...parsed.querySelectorAll("svg path title")].map((title) => title.textContent);
  expect(titles).toHaveLength(18);
  expect(titles[0]).toBe("I · Stare Miasto");
  expect(titles[17]).toBe("XVIII · Nowa Huta");
  expect(titles.every((title) => Boolean(title?.trim()))).toBe(true);
});

it("offers all 18 official districts as named keyboard controls, independently of search reference availability", () => {
  render(<HomeDistrictMap />);
  fireEvent.click(screen.getByText("Wybierz dzielnicę z listy (18)"));
  const list = screen.getByRole("list", { name: "Dzielnice administracyjne Krakowa" });
  expect(within(list).getAllByRole("button")).toHaveLength(18);
  expect(within(list).getByRole("button", { name: "Mistrzejowice" })).toBeVisible();
  expect(within(list).getByRole("button", { name: "Wzgórza Krzesławickie" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Kazimierz" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zobacz cały Kraków" })).toHaveAttribute("href", "/wynajem/krakow");
});

it("selects by keyboard, announces the district and never fabricates a district search link or count", async () => {
  const user = userEvent.setup();
  render(<HomeDistrictMap />);
  await user.tab();
  expect(screen.getByText("Wybierz dzielnicę z listy (18)")).toHaveFocus();
  await user.keyboard("{Enter}");
  const first = screen.getByRole("button", { name: "Stare Miasto" });
  await user.tab();
  expect(first).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(first).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("status")).toHaveTextContent("I · Stare Miasto");
  expect(screen.getByRole("status")).toHaveTextContent("Wyszukiwanie w pełnych granicach tej dzielnicy nie jest jeszcze dostępne");
  await user.tab();
  await user.keyboard(" ");
  expect(first).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("button", { name: "Grzegórzki" })).toHaveAttribute("aria-pressed", "true");
  expect(document.querySelector('a[href="/wynajem/krakow/stare-miasto"]')).toBeNull();
  expect(document.body.textContent).not.toMatch(/zł|\d+ ofert/);
});

it("pointer selection and native buttons share state, while clicks outside the geometry do not select another district", () => {
  const { container } = render(<HomeDistrictMap />);
  fireEvent.click(screen.getByText("Wybierz dzielnicę z listy (18)"));
  fireEvent.click(container.querySelector('[data-district="18"]')!);
  expect(screen.getByRole("button", { name: "Nowa Huta" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("status")).toHaveTextContent("XVIII · Nowa Huta");
  fireEvent.click(container.querySelector("svg")!);
  expect(screen.getByRole("button", { name: "Nowa Huta" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "Bieńczyce" }));
  expect(screen.getByRole("button", { name: "Nowa Huta" })).toHaveAttribute("aria-pressed", "false");
  expect(container.querySelector('[data-selected="16"]')).toBeInTheDocument();
});

it("provides data attribution without external map calls, private pins or hidden duplicate keyboard controls", () => {
  const { container } = render(<HomeDistrictMap />);
  expect(screen.getByRole("link", { name: /Granice: Gmina Miejska Kraków/ })).toHaveAttribute("href", "/zrodla/mapa-krakowa");
  expect(container.querySelectorAll("svg path")).toHaveLength(18);
  expect(container.querySelectorAll("svg [tabindex], iframe, img, script")).toHaveLength(0);
  expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
});
