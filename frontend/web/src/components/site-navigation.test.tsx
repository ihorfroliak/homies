import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";

import { SiteNavigation } from "./site-navigation";

afterEach(cleanup);

it("opens by keyboard and Escape returns focus to the labelled trigger", async () => {
  const user = userEvent.setup();
  render(<SiteNavigation><li><a href="#results">Oferty</a></li></SiteNavigation>);
  const trigger = screen.getByRole("button", { name: "Menu" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(trigger).toHaveAttribute("aria-controls", "site-navigation");
  await user.tab(); await user.keyboard("{Enter}"); await user.tab();
  expect(screen.getByRole("link", { name: "Oferty" })).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(trigger).toHaveFocus();
  expect(trigger).toHaveAttribute("aria-expanded", "false");
});

it("closes on navigation and outside interaction, without duplicating destinations", () => {
  render(<><SiteNavigation><li><a href="#results">Oferty</a></li></SiteNavigation><button>Poza menu</button></>);
  fireEvent.click(screen.getByRole("button", { name: "Menu" }));
  expect(screen.getAllByRole("link", { name: "Oferty" })).toHaveLength(1);
  fireEvent.click(screen.getByRole("link", { name: "Oferty" }));
  expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(screen.getByRole("button", { name: "Menu" }));
  fireEvent.pointerDown(screen.getByRole("button", { name: "Poza menu" }));
  expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
});

it("keeps the initiating menu action available while a dialog owns focus", () => {
  render(<><SiteNavigation><li><button>Zaloguj</button></li></SiteNavigation><div role="dialog" aria-label="Logowanie"><input aria-label="E-mail" /></div></>);
  fireEvent.click(screen.getByRole("button", { name: "Menu" }));
  fireEvent.click(screen.getByRole("button", { name: "Zaloguj" }));
  fireEvent.pointerDown(screen.getByRole("textbox", { name: "E-mail" }));
  expect(screen.getByRole("button", { name: "Zamknij menu" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "Zaloguj" })).toBeInTheDocument();
});
