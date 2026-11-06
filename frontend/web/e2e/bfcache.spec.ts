import { expect, test, type Page } from "@playwright/test";

/**
 * FE-UX-KRK-002R UX-R5: a real back/forward cache restore, not ordinary history.
 * Playwright turns the cache off by default, so this file turns it back on. A run
 * only counts as coverage when the browser itself reports pageshow.persisted; when
 * it does not, the test records that, with Chromium's reasons, and proves nothing
 * about the restore path. Synthetic pageshow events live in unit tests, labelled so.
 */
test.skip(process.env.E2E_BACKEND !== "1", "needs the API with the E2E seed");
test.use({ launchOptions: { ignoreDefaultArgs: ["--disable-back-forward-cache"] } });

async function watch(page: Page) {
  await page.addInitScript(() => {
    (window as unknown as { __shows: boolean[] }).__shows = [];
    window.addEventListener("pageshow", (event) => (window as unknown as { __shows: boolean[] }).__shows.push(event.persisted));
  });
}
const restored = (page: Page) => page.evaluate(() => (window as unknown as { __shows: boolean[] }).__shows.at(-1) === true);

async function reasons(page: Page, browserName: string): Promise<() => string[]> {
  if (browserName !== "chromium") return () => [];
  const found: string[] = [];
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Page.enable");
  cdp.on("Page.backForwardCacheNotUsed", (event: { notRestoredExplanations: { reason: string }[] }) => {
    for (const item of event.notRestoredExplanations) found.push(item.reason);
  });
  return () => found;
}

function report(name: string, isRestored: boolean, why: string[]) {
  test.info().annotations.push({ type: isRestored ? "bfcache-exercised" : "bfcache-not-exercised", description: `${name}: ${why.join(", ") || "no reason reported"}` });
  console.log(`[bfcache] ${test.info().project.name} ${name}: persisted=${isRestored} reasons=${why.join(",") || "-"}`);
}

test("sort select after Back shows what the URL says, on whichever path the browser took", async ({ page, browserName }) => {
  await watch(page);
  const why = await reasons(page, browserName);
  await page.goto("/wynajem/krakow");
  const requests: string[] = [];
  await page.locator("#sort").selectOption("najtansze");
  await expect(page).toHaveURL(/sort=najtansze/);
  page.on("request", (r) => {
    if (r.isNavigationRequest()) requests.push(r.url());
  });
  await page.goBack();
  await expect(page).toHaveURL(/\/wynajem\/krakow$/);
  await page.waitForTimeout(800);
  report("sort", await restored(page), why());
  await expect(page.locator("#sort")).toHaveValue("najnowsze");
  // The restored select must not submit itself.
  await expect(page).toHaveURL(/\/wynajem\/krakow$/);
  expect(requests.filter((u) => u.includes("sort=najtansze"))).toEqual([]);
});

test("filter form after Back shows what the URL says, and its fields work", async ({ page, browserName }) => {
  await watch(page);
  const why = await reasons(page, browserName);
  await page.goto("/wynajem/krakow");
  await page.locator("#filtry-panel summary").click();
  await page.getByLabel("Pokoje (od)").fill("4");
  await page.getByRole("button", { name: "Pokaż 1 oferta" }).click();
  await expect(page).toHaveURL(/pokoje_od=4$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/wynajem\/krakow$/);
  await page.waitForTimeout(800);
  report("filters", await restored(page), why());
  if (!(await page.getByLabel("Pokoje (od)").isVisible())) await page.locator("#filtry-panel summary").click();
  await expect(page.getByLabel("Pokoje (od)")).toHaveValue("");
  await expect(page.getByLabel("Maks. koszt na start (zł)")).toBeEnabled();
  await page.getByLabel("Pokoje (od)").fill("3");
  await expect(page.getByRole("button", { name: "Pokaż 3 oferty" })).toBeVisible();
});
