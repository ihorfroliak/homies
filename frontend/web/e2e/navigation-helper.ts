import { type Page } from "@playwright/test";

/** Reach the same real actions through the mobile disclosure or desktop bar. */
export async function openNavigation(page: Page) {
  const trigger = page.getByRole("button", { name: "Menu", exact: true });
  if (await trigger.isVisible()) await trigger.click();
}
