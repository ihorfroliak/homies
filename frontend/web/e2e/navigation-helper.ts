import { type Page } from "@playwright/test";

/** Reach the same real actions through the mobile disclosure or desktop bar. */
export async function openNavigation(page: Page) {
  // The menu button appears on hydration (without JavaScript it could not work).
  await page.locator('button[aria-controls="site-navigation"][data-ready="true"]').waitFor({ state: "attached" });
  const trigger = page.getByRole("button", { name: "Menu", exact: true });
  if (await trigger.isVisible()) await trigger.click();
}
