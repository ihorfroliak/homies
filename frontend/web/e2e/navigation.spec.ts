import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { openNavigation } from "./navigation-helper";

test("navigation stays usable at narrow widths, closes on Escape and preserves auth return focus", async ({ page }, info) => {
  await page.goto("/");
  if (info.project.name === "mobile") {
    await page.setViewportSize({ width: 360, height: 800 });
    const trigger = page.getByRole("button", { name: "Menu", exact: true });
    await expect(trigger).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Nawigacja główna" })).toBeHidden();
    await trigger.click();
    await expect(page.getByRole("button", { name: "Wyloguj się", exact: true })).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await expect(trigger).toHaveAttribute("aria-expanded", "false");
  }
  await openNavigation(page);
  const nav = page.getByRole("navigation", { name: "Nawigacja główna" });
  const login = nav.getByRole("button", { name: "Zaloguj się", exact: true });
  await login.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog").getByLabel("E-mail", { exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(login).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(scan.violations.map((violation) => violation.id)).toEqual([]);
});

test("district list expands by keyboard and remains honest about search coverage", async ({ page }) => {
  await page.goto("/");
  const disclosure = page.getByText("Wybierz dzielnicę z listy (18)", { exact: true });
  await disclosure.focus(); await page.keyboard.press("Enter");
  const list = page.getByRole("list", { name: "Dzielnice administracyjne Krakowa" });
  await expect(list.getByRole("button")).toHaveCount(18);
  await list.getByRole("button", { name: "Stare Miasto", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "I · Stare Miasto" })).toContainText("nie jest jeszcze dostępne");
  await expect(page.getByLabel("Miasto", { exact: true })).toHaveValue("Kraków");
});

test("home switches to the real public map on demand and preserves district choice and form values", async ({ page }) => {
  test.skip(process.env.E2E_BACKEND !== "1", "needs the disposable seeded backend");
  const mapRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/bff/v1/classifieds/map")) mapRequests.push(request.url()); });
  await page.goto("/");
  await page.getByText("Wybierz dzielnicę z listy (18)", { exact: true }).click();
  await page.getByRole("button", { name: "Stare Miasto", exact: true }).click();
  await page.getByLabel("Maks. koszt miesięczny (zł)").fill("4200");
  expect(mapRequests).toHaveLength(0);
  const response = page.waitForResponse((r) => r.url().includes("/bff/v1/classifieds/map") && r.status() === 200);
  await page.getByRole("button", { name: "Mapa ofert", exact: true }).click();
  const payload = await (await response).json();
  expect(payload.total).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: "Mieszkania na mapie Krakowa" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Otwórz mapę z filtrami/ })).toHaveAttribute("href", "/wynajem/krakow?widok=mapa");
  await page.getByRole("button", { name: "Dzielnice", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stare Miasto", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Maks. koszt miesięczny (zł)")).toHaveValue("4200");
});
