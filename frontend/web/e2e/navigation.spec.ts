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
