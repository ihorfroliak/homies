import { expect, test } from "@playwright/test";

/**
 * Performance budget (FE-001 §7): compressed JavaScript on the first view.
 * The map library is lazy-loaded and must never be part of the initial load.
 * Measured from Resource Timing after `load` (not `networkidle`: router
 * prefetches may stay open and are not part of the first view).
 */
const BUDGET_JS_BYTES = 220 * 1024;

test("home stays within the JavaScript budget and does not load the map", async ({ page }) => {
  await page.goto("/", { waitUntil: "load" });
  await page.waitForTimeout(1000);
  const scripts = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .filter((e) => (e as PerformanceResourceTiming).initiatorType === "script" || e.name.endsWith(".js"))
      .map((e) => ({ name: e.name, bytes: (e as PerformanceResourceTiming).encodedBodySize })),
  );
  const total = scripts.reduce((sum, s) => sum + s.bytes, 0);
  test.info().annotations.push({ type: "js-bytes", description: String(total) });
  expect(scripts.length).toBeGreaterThan(0);
  expect(total).toBeLessThan(BUDGET_JS_BYTES);
  expect(scripts.some((s) => s.name.includes("maplibre"))).toBe(false);
});
