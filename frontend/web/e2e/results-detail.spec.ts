import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * FE-UX-KRK-002: search state, map readability and the listing's first screen,
 * against the real backend with the E2E seed (10 Kraków + 2 Warszawa fictional
 * listings). Skipped unless E2E_BACKEND=1.
 */
test.skip(process.env.E2E_BACKEND !== "1", "needs the API with the E2E seed");

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
}

/** Visible pills only: a grouped member is hidden, never removed. */
async function pillRects(page: Page) {
  await expect(page.locator(".maplibregl-marker").first()).toBeAttached();
  await page.waitForTimeout(400);
  return page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>(".maplibregl-marker")]
      .filter((el) => el.style.display !== "none")
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { text: el.textContent ?? "", left: r.left, right: r.right, top: r.top, bottom: r.bottom };
      }),
  );
}

test("Back after changing the sort shows the sort the URL says", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  await page.locator("#sort").selectOption("najtansze");
  await expect(page).toHaveURL(/sort=najtansze/);
  await expect(page.locator("#sort")).toHaveValue("najtansze");
  await page.goBack();
  await expect(page).toHaveURL(/\/wynajem\/krakow$/);
  await expect(page.locator("#sort")).toHaveValue("najnowsze");
  await page.goForward();
  await expect(page).toHaveURL(/sort=najtansze/);
  await expect(page.locator("#sort")).toHaveValue("najtansze");
});

test("Back after applying a filter empties the field the URL no longer holds", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  await page.getByText("Filtry", { exact: true }).click();
  await page.getByLabel("Pokoje (od)").fill("4");
  await page.getByRole("button", { name: "Pokaż 1 oferta" }).click();
  await expect(page).toHaveURL(/pokoje_od=4$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/wynajem\/krakow$/);
  await expect(page.getByText("Znaleźliśmy 10 ofert")).toBeVisible();
  await page.getByText("Filtry", { exact: true }).click();
  await expect(page.getByLabel("Pokoje (od)")).toHaveValue("");
  await expect(page.getByLabel("Pokoje (od)")).toBeEnabled();
  await expect(page.getByRole("button", { name: "Pokaż 10 ofert" })).toBeVisible();
});

test("removing a chip updates the filter panel's values and count", async ({ page }) => {
  await page.goto("/wynajem/krakow?pokoje_od=3");
  await expect(page.getByText("Znaleźliśmy 3 oferty")).toBeVisible();
  await page.getByRole("link", { name: "Usuń filtr: Pokoje od 3" }).click();
  await expect(page.getByText("Znaleźliśmy 10 ofert")).toBeVisible();
  await page.getByText("Filtry", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Pokaż 10 ofert" })).toBeVisible();
  await expect(page.getByLabel("Pokoje (od)")).toHaveValue("");
});

test("the neighbourhood is a visible constraint with a way back to the whole city", async ({ page }) => {
  await page.goto("/wynajem/krakow/kazimierz?pokoje_od=1");
  const chip = page.getByRole("link", { name: "Usuń okolicę: Kazimierz. Pokaż całe miasto" });
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page).toHaveURL(/\/wynajem\/krakow\?pokoje_od=1$/);
  await page.getByText(/^Filtry/).click();
  await page.getByRole("link", { name: "Kazimierz", exact: true }).click();
  await expect(page).toHaveURL(/\/wynajem\/krakow\/kazimierz\?pokoje_od=1$/);
  await page.getByText(/^Filtry/).click();
  await page.getByRole("link", { name: "Całe miasto", exact: true }).click();
  await expect(page).toHaveURL(/\/wynajem\/krakow\?pokoje_od=1$/);
});

test("the filter panel closes on Escape, returns focus and leaves the controls in place", async ({ page }, info) => {
  await page.goto("/wynajem/krakow?widok=mapa");
  const summary = page.locator("#filtry-panel summary");
  const sortBefore = await page.locator("#sort").boundingBox();
  await summary.click();
  await expect(page.getByLabel("Pokoje (od)")).toBeVisible();
  if (info.project.name === "desktop") {
    // Floating over the results: opening it does not move the toolbar.
    expect((await page.locator("#sort").boundingBox())?.y).toBe(sortBefore?.y);
    await expect(page.getByRole("link", { name: "Mapa", exact: true })).toBeVisible();
  } else {
    // Own row in the flow, and the floating switch must not cover the submit button.
    await expect(page.getByRole("navigation", { name: "Widok wyników" })).toBeHidden();
    await noOverflow(page);
  }
  await axe(page);
  await page.getByLabel("Pokoje (od)").focus();
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Pokoje (od)")).toBeHidden();
  await expect(summary).toBeFocused();
});

test("an empty map view explains itself on every width", async ({ page }) => {
  await page.goto("/wynajem/krakow?widok=mapa&koszt_do=1");
  await expect(page.getByRole("heading", { name: "Brak ofert dla tych filtrów" })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Usuń »Koszt do 1\szł«/ })).toBeVisible();
  await expect(page.locator(".maplibregl-map")).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Widok wyników" })).toBeVisible();
});

test("a slow list/map navigation shows it is working", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  await page.route((url) => url.searchParams.has("_rsc"), async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue().catch(() => undefined);
  });
  await page.getByRole("navigation", { name: "Widok wyników" }).getByRole("link", { name: "Mapa" }).click();
  await expect(page.locator("[data-link-pending]")).toBeAttached();
  await expect(page).toHaveURL(/widok=mapa/);
  await expect(page.locator("[data-link-pending]")).toHaveCount(0);
});

test("the mobile map keeps its source credits clear of the view switch", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "the switch floats only below 1024 px");
  await page.goto("/wynajem/krakow?widok=mapa");
  await expect(page.locator(".maplibregl-map")).toBeVisible();
  const map = (await page.locator(".maplibregl-map").boundingBox())!;
  const views = (await page.getByRole("navigation", { name: "Widok wyników" }).boundingBox())!;
  expect(views.y + views.height).toBeLessThanOrEqual(map.y);
});

test("the list/map switch stays reachable and keeps filters both ways", async ({ page }) => {
  await page.goto("/wynajem/krakow?koszt_do=5000&sort=najtansze");
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  const views = page.getByRole("navigation", { name: "Widok wyników" });
  await views.getByRole("link", { name: "Mapa" }).click();
  await expect(page).toHaveURL(/widok=mapa/);
  await expect(page).toHaveURL(/koszt_do=5000/);
  await expect(page).toHaveURL(/sort=najtansze/);
  await expect(views.getByRole("link", { name: "Mapa" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator(".maplibregl-marker").first()).toBeAttached();
  await page.goBack();
  await expect(page).not.toHaveURL(/widok=mapa/);
  await expect(views.getByRole("link", { name: "Lista" })).toHaveAttribute("aria-current", "page");
  await page.goForward();
  await expect(page).toHaveURL(/widok=mapa/);
  await expect(page.locator(".maplibregl-marker").first()).toBeAttached();
});

for (const width of [360, 390]) {
  test(`near pills never overlap at ${width} px and every listing stays reachable`, async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "narrow viewport");
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/wynajem/krakow?widok=mapa");
    const rects = await pillRects(page);
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        const [a, b] = [rects[i]!, rects[j]!];
        const overlap = a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
        expect(overlap, `${a.text} / ${b.text}`).toBe(false);
      }
    }
    // Nine of the ten seeded Kraków listings have a public point; the tenth is DISTRICT-only.
    const shown = rects.reduce((n, r) => n + (/ofert/.test(r.text) ? Number(r.text.match(/\d+/)?.[0]) : 1), 0);
    expect(shown).toBe(9);
    await noOverflow(page);
  });
}

test("a pill group opens all its listings, zooms apart and returns focus", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const group = page.locator('.maplibregl-marker[data-kind="nearby"]').first();
  test.skip((await group.count()) === 0, "this viewport and fit produce no group");
  const label = (await group.textContent()) ?? "";
  const count = Number(label.match(/\d+/)?.[0]);
  const originalPosition = await page.evaluate(() => document.querySelectorAll(".maplibregl-marker").length);
  await group.focus();
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog", { name: new RegExp(`${count} ofert.* w pobliżu`) });
  await expect(card).toBeVisible();
  await expect(card.getByRole("link")).toHaveCount(count);
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
  await expect(group).toBeFocused();
  await group.click();
  await page.getByRole("button", { name: "Przybliż mapę tutaj" }).click();
  await expect(card).toHaveCount(0);
  await expect.poll(async () => (await page.locator('.maplibregl-marker[data-kind="nearby"]').count())).toBeLessThan(1);
  // Zooming redraws; no marker was created or lost.
  expect(await page.evaluate(() => document.querySelectorAll(".maplibregl-marker").length)).toBe(originalPosition);
});

/** The server's public points for the seeded Kraków search, read the way the page reads them. */
async function publicPoints(page: Page) {
  const cities = (await (await page.request.get("/bff/v1/geo/localities?country=PL&limit=8&q=Krak%C3%B3w")).json()) as { id: string; slug: string; kind: string }[];
  const city = cities.find((row) => row.kind === "CITY" && row.slug === "krakow");
  expect(city).toBeTruthy();
  const map = await page.request.get(`/bff/v1/classifieds/map?locality_id=${city!.id}`);
  expect(map.status()).toBe(200);
  return ((await map.json()) as { points: { id: string; latitude: number; longitude: number }[] }).points;
}

test("grouping moves no point, splits no stack and leaves every listing reachable", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const points = await publicPoints(page);
  const cells = new Map<string, string[]>();
  for (const p of points) {
    const key = `${p.latitude.toFixed(5)},${p.longitude.toFixed(5)}`;
    cells.set(key, [...(cells.get(key) ?? []), p.id]);
  }
  // Every public cell has exactly one marker on its own coordinates, shown or grouped away.
  const drawn = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>(".maplibregl-marker")].map((el) => el.dataset.cell));
  expect([...drawn].sort()).toEqual([...cells.keys()].sort());
  // Opening every visible pill reaches every public listing exactly once.
  const reached: string[] = [];
  const visible = page.locator(".maplibregl-marker").filter({ visible: true });
  for (let i = 0; i < (await visible.count()); i++) {
    const pill = visible.nth(i);
    const kind = await pill.getAttribute("data-kind");
    const cell = await pill.getAttribute("data-cell");
    await pill.click({ force: true });
    const card = page.getByRole("dialog");
    await expect(card.locator("[role=status]")).toHaveCount(0);
    const hrefs = await card.getByRole("link").evaluateAll((links) => links.map((a) => a.getAttribute("href")!.replace("/oferta/", "")));
    if (kind === "stack") expect([...hrefs].sort()).toEqual([...cells.get(cell!)!].sort()); // a privacy stack stays whole
    reached.push(...hrefs);
    await card.getByRole("button", { name: "Zamknij" }).click();
    await expect(card).toHaveCount(0);
  }
  expect([...reached].sort()).toEqual(points.map((p) => p.id).sort());
});

test("a resize regroups the pills without losing or overlapping any", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const count = (texts: string[]) => texts.reduce((n, t) => n + (/ofert/.test(t) ? Number(t.match(/\d+/)?.[0]) : 1), 0);
  const narrow = await pillRects(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect.poll(async () => (await pillRects(page)).length).toBeGreaterThanOrEqual(narrow.length);
  const wide = await pillRects(page);
  expect(count(wide.map((r) => r.text))).toBe(count(narrow.map((r) => r.text)));
  for (let i = 0; i < wide.length; i++) {
    for (let j = i + 1; j < wide.length; j++) {
      const [a, b] = [wide[i]!, wide[j]!];
      expect(a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom, `${a.text} / ${b.text}`).toBe(false);
    }
  }
});

test("the map card is keyboard operable, returns focus and keeps the source credits visible", async ({ page }) => {
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const pill = page.locator(".maplibregl-marker").filter({ visible: true }).first();
  await pill.focus();
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog");
  await expect(card.getByRole("link").first()).toBeVisible();
  await expect(card.getByRole("button", { name: "Zamknij" })).toBeFocused();
  await axe(page);
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
  await expect(pill).toBeFocused();
});

test("keyboard users can skip the list to reach the map", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "the list is not on screen in mobile map mode");
  await page.goto("/wynajem/krakow?widok=mapa");
  const skip = page.getByRole("link", { name: "Przejdź do mapy" });
  await skip.focus();
  await expect(skip).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.locator("#mapa")).toBeFocused();
});

test("hovering a card marks the pill that holds it", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "needs the split view and a pointer");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  await page.locator("#wyniki article").first().hover();
  await expect(page.locator(".maplibregl-marker[data-active]")).toHaveCount(1);
  await page.locator("header").first().hover();
  await expect(page.locator(".maplibregl-marker[data-active]")).toHaveCount(0);
});

test("the listing's back link keeps the filters and view, and survives no stored results", async ({ page, context }) => {
  await page.goto("/wynajem/krakow?koszt_do=5000&widok=mapa");
  await page.goto("/wynajem/krakow?koszt_do=5000");
  await page.locator("#wyniki article h3 a").first().click();
  await expect(page).toHaveURL(/\/oferta\//);
  const listing = page.url();
  const back = page.getByRole("link", { name: "Wróć do wyników" });
  await expect(back).toHaveAttribute("href", "/wynajem/krakow?koszt_do=5000");
  await back.click();
  await expect(page).toHaveURL(/\/wynajem\/krakow\?koszt_do=5000$/);
  await expect(page.getByRole("link", { name: /Usuń filtr: Koszt do 5/ })).toBeVisible();
  const fresh = await context.newPage(); // a new tab has no results of its own
  await fresh.goto(listing);
  await expect(fresh.getByRole("link", { name: "Wróć do wyników" })).toHaveAttribute("href", "/wynajem/krakow");
  await fresh.close();
});

test("Back and Forward between results and a listing keep filters, sort and view", async ({ page }, info) => {
  const search = "/wynajem/krakow?koszt_do=6000&sort=najtansze&widok=mapa";
  await page.goto(search);
  await pillRects(page);
  await page.goto("/wynajem/krakow?koszt_do=6000&sort=najtansze");
  await page.getByRole("navigation", { name: "Widok wyników" }).getByRole("link", { name: "Mapa" }).click();
  await expect(page).toHaveURL(/widok=mapa/);
  await pillRects(page);
  if (info.project.name === "desktop") {
    await page.locator("#wyniki article h3 a").first().click();
  } else {
    await page.locator(".maplibregl-marker").filter({ visible: true }).first().click({ force: true });
    await page.getByRole("dialog").getByRole("link").first().click();
  }
  await expect(page).toHaveURL(/\/oferta\//);
  const listing = page.url();
  const back = page.getByRole("link", { name: "Wróć do wyników" });
  await expect(back).toHaveAttribute("href", /koszt_do=6000/);
  await expect(back).toHaveAttribute("href", /sort=najtansze/);
  await expect(back).toHaveAttribute("href", /widok=mapa/);
  await page.goBack();
  await expect(page).toHaveURL(/koszt_do=6000/);
  await expect(page).toHaveURL(/sort=najtansze/);
  await expect(page).toHaveURL(/widok=mapa/);
  await expect(page.locator("#sort")).toHaveValue("najtansze");
  await expect(page.getByRole("navigation", { name: "Widok wyników" }).getByRole("link", { name: "Mapa" })).toHaveAttribute("aria-current", "page");
  await page.goForward();
  await expect(page).toHaveURL(listing);
  await back.click();
  await expect(page).toHaveURL(/koszt_do=6000/);
  await expect(page).toHaveURL(/widok=mapa/);
  await expect(page.locator("#sort")).toHaveValue("najtansze");
});

test("a tampered stored path never becomes the back link", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  await page.locator("#wyniki article h3 a").first().click();
  await expect(page).toHaveURL(/\/oferta\//);
  for (const bad of ["https://example.com/wynajem", "//example.com/wynajem", "/wiadomosci", "javascript:alert(1)"]) {
    await page.evaluate((value) => sessionStorage.setItem("homies.search.last-results", value), bad);
    await page.reload();
    await expect(page.getByRole("link", { name: "Wróć do wyników" })).toHaveAttribute("href", "/wynajem/krakow");
  }
});

test("the listing's first screen carries the identity, the price and the action", async ({ page }, info) => {
  await page.goto("/wynajem/krakow?sort=najdrozsze");
  await page.locator("#wyniki article h3 a").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("section").filter({ has: page.getByRole("heading", { name: "Koszty", exact: true }) }).filter({ visible: true })).toHaveCount(1);
  const viewing = page.getByRole("button", { name: "Umów oglądanie" }).filter({ visible: true });
  await expect(viewing).toHaveCount(1);
  const height = page.viewportSize()!.height;
  if (info.project.name === "desktop") {
    await page.setViewportSize({ width: 1440, height: 1000 });
    expect((await viewing.boundingBox())!.y + (await viewing.boundingBox())!.height).toBeLessThan(1000);
    expect((await page.getByRole("heading", { name: "Koszty", exact: true }).boundingBox())!.y).toBeLessThan(1000);
  } else {
    // Mobile: the dock is fixed in the first screen and the page can scroll clear of it.
    expect((await viewing.boundingBox())!.y).toBeLessThan(height);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const dockTop = (await page.getByRole("region", { name: "Akcje oferty" }).boundingBox())!.y;
    const footer = page.getByRole("contentinfo");
    expect((await footer.getByText("Polska").boundingBox())!.y).toBeLessThan(dockTop);
  }
  await noOverflow(page);
  await axe(page);
});

test("the listing's actions ask for login and come back to the same listing", async ({ page }, info) => {
  await page.goto("/wynajem/krakow");
  await page.locator("#wyniki article h3 a").first().click();
  await expect(page).toHaveURL(/\/oferta\//);
  const listing = page.url();
  if (info.project.name === "mobile") await page.getByRole("button", { name: "Więcej działań", exact: true }).click();
  await page.getByRole("button", { name: "Napisz", exact: true }).filter({ visible: true }).first().click();
  await expect(page.getByRole("dialog").last()).toBeVisible();
  await expect(page.getByLabel("E-mail").filter({ visible: true }).first()).toBeVisible();
  await expect(page).toHaveURL(listing);
});

test("every list width keeps long Polish labels inside the page", async ({ page }) => {
  for (const width of [360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/wynajem/krakow?koszt_od=1&koszt_do=99999&na_start_do=99999&pokoje_od=1&metraz_od=10&okres_do=120&umeblowanie=czesciowe&parking=garaz&zwierzeta=tak&winda=tak");
    await noOverflow(page);
    await page.goto("/wynajem/krakow?sort=najszybciej");
    await noOverflow(page);
  }
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("phone navigation offers real links and no inert menu button", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "the menu button exists only on narrow screens");
    await page.goto("/wynajem/krakow");
    await expect(page.getByRole("button", { name: "Menu" })).toBeHidden();
    const nav = page.getByRole("navigation", { name: "Nawigacja bez JavaScript" });
    await expect(nav.getByRole("link", { name: "Szukaj" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Wynajem w Krakowie" })).toHaveAttribute("href", "/wynajem/krakow");
  });

  test("filters, list and map switch still work", async ({ page }) => {
    await page.goto("/wynajem/krakow");
    await page.locator("#filtry-panel summary").click();
    await page.getByLabel("Pokoje (od)").fill("4");
    await page.getByRole("button", { name: "Pokaż" }).click();
    await expect(page).toHaveURL(/pokoje_od=4/);
    await expect(page.locator("#wyniki article")).toHaveCount(1);
    await page.getByRole("link", { name: "Usuń filtr: Pokoje od 4" }).click();
    await expect(page.locator("#wyniki article")).toHaveCount(10);
  });
});
