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

test("a sort chosen as soon as the page appears still applies, hydrated or not", async ({ page }) => {
  await page.goto("/wynajem/krakow", { waitUntil: "commit" });
  await page.locator("#sort").selectOption("najtansze");
  await expect(page).toHaveURL(/sort=najtansze/, { timeout: 10_000 });
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

test("the filter panel closes on Escape, returns focus and leaves the controls in place", async ({ page }) => {
  await page.goto("/wynajem/krakow?widok=mapa");
  const summary = page.locator("#filtry-panel summary");
  const sortBefore = await page.locator("#sort").boundingBox();
  await summary.click();
  await expect(page.getByLabel("Pokoje (od)")).toBeVisible();
  if (page.viewportSize()!.width >= 768) {
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

test("a stack above ten pages through its listings on real data", async ({ page }) => {
  test.skip(process.env.E2E_ENGAGEMENT !== "1", "the large same-cell stack comes from the engagement fixtures");
  await page.goto("/wynajem/lublin?widok=mapa");
  await pillRects(page);
  const stack = page.locator('.maplibregl-marker[data-kind="stack"]').first();
  const total = Number((await stack.textContent())?.match(/\d+/)?.[0]);
  expect(total).toBeGreaterThan(10);
  await stack.click({ force: true });
  const card = page.getByRole("dialog");
  const links = card.getByRole("link");
  await expect(links).toHaveCount(10);
  const more = card.getByRole("button", { name: /Pokaż kolejne/ });
  await expect(more).toContainText(`z ${total}`);
  while (await more.count()) {
    const before = await links.count();
    await more.click();
    await expect.poll(() => links.count()).toBeGreaterThan(before);
    await expect(links.nth(before)).toBeFocused();
  }
  const hrefs = await links.evaluateAll((all) => all.map((a) => a.getAttribute("href")));
  expect(new Set(hrefs).size).toBe(hrefs.length);
  expect(hrefs.length).toBeGreaterThan(10);
});

/** UX-R3: the open card must describe the map as it is now. */
async function openGroup(page: Page) {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const group = page.locator('.maplibregl-marker[data-kind="nearby"]').first();
  await expect(group).toBeAttached();
  return group;
}
const zoomIn = (page: Page) => page.getByRole("button", { name: "Zoom in" });
const zoomOut = (page: Page) => page.getByRole("button", { name: "Zoom out" });
const settle = (page: Page) => page.waitForTimeout(700);

test("zooming a group apart closes its card; zooming back regroups", async ({ page }) => {
  const group = await openGroup(page);
  const before = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>(".maplibregl-marker")].map((el) => el.dataset.cell).sort());
  await group.click({ force: true });
  const card = page.getByRole("dialog", { name: /w pobliżu/ });
  await expect(card).toBeVisible();
  for (let i = 0; i < 4 && (await page.locator('.maplibregl-marker[data-kind="nearby"]').count()) > 0; i++) {
    await zoomIn(page).click();
    await settle(page);
  }
  await expect(page.locator('.maplibregl-marker[data-kind="nearby"]')).toHaveCount(0);
  // The group no longer exists, so a card naming it must not remain.
  await expect(card).toHaveCount(0);
  for (let i = 0; i < 4 && (await page.locator('.maplibregl-marker[data-kind="nearby"]').count()) === 0; i++) {
    await zoomOut(page).click();
    await settle(page);
  }
  await expect(page.locator('.maplibregl-marker[data-kind="nearby"]').first()).toBeAttached();
  const after = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>(".maplibregl-marker")].map((el) => el.dataset.cell).sort());
  expect(after).toEqual(before); // same public cells throughout
});

test("a card whose group survives a zoom stays open with its focus", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const stack = page.locator('.maplibregl-marker[data-kind="stack"]').first();
  await stack.click({ force: true });
  const card = page.getByRole("dialog", { name: /w tym miejscu/ });
  await expect(card).toBeVisible();
  await zoomIn(page).click();
  await settle(page);
  await expect(card).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(1);
});

test("a group dissolved while focus is inside its card moves focus to a real pill", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "needs a wheel: keyboard focus stays in the card while the map zooms");
  const group = await openGroup(page);
  await group.focus();
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog", { name: /w pobliżu/ });
  await expect(card.getByRole("button", { name: "Zamknij" })).toBeFocused();
  const box = (await page.locator(".maplibregl-map").boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 60);
  for (let i = 0; i < 12 && (await card.count()) > 0; i++) {
    await page.mouse.wheel(0, -500);
    await settle(page);
  }
  await expect(card).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.activeElement?.closest(".maplibregl-marker") !== null)).toBe(true);
});

test("a resize keeps the card only while its group still exists on the map", async ({ page }) => {
  const group = await openGroup(page);
  await group.focus();
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog", { name: /w pobliżu/ });
  await expect(card).toBeVisible();
  const members = await card.getByRole("heading").textContent();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await settle(page);
  // Same zoom, same pixel distances: the group exists, so the card rightly stays and still names it.
  await expect(page.locator('.maplibregl-marker[data-kind="nearby"]').filter({ visible: true })).toHaveCount(1);
  await expect(card.getByRole("heading")).toHaveText(members!);
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
  await expect(group).toBeFocused();
});

test("a privacy stack stays one card and is never split by zooming", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const stack = page.locator('.maplibregl-marker[data-kind="stack"]').first();
  const cell = await stack.getAttribute("data-cell");
  const label = await stack.textContent();
  for (let i = 0; i < 5; i++) {
    await zoomIn(page).click();
    await settle(page);
  }
  const same = page.locator(`.maplibregl-marker[data-cell="${cell}"]`);
  await expect(same).toHaveCount(1);
  await expect(same).toHaveText(label!);
});

/** UX-R4: a reopened card reads again; BFF answers are injected to change or fail deterministically. */
test("reopening a card shows the current price, and a removed or failing listing is said, not remembered", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/wynajem/krakow?widok=mapa");
  await pillRects(page);
  const pill = page.locator('.maplibregl-marker[data-kind="price"]').first();
  const card = page.getByRole("dialog");
  let reads = 0;
  let answer: "real" | "changed" | "gone" | "down" = "real";
  await page.route(/\/bff\/v1\/classifieds\/[0-9a-f-]{36}$/, async (route) => {
    reads++;
    if (answer === "gone") return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
    if (answer === "down") return route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    const response = await route.fetch();
    const body = await response.json() as Record<string, unknown>;
    if (answer === "changed") body.monthly_total_estimate = 123400;
    return route.fulfill({ response, json: body });
  });
  await pill.click({ force: true });
  await expect(card.getByRole("link")).toHaveCount(1);
  const original = await card.locator("p").first().textContent();
  await card.getByRole("button", { name: "Zamknij" }).click();
  expect(reads).toBe(1);

  answer = "changed";
  await pill.click({ force: true });
  await expect(card).toContainText("1 234");
  expect(reads).toBe(2);
  await card.getByRole("button", { name: "Zamknij" }).click();

  answer = "down";
  await pill.click({ force: true });
  await expect(card).toContainText("Nie udało się wczytać");
  await expect(card.getByRole("link")).toHaveCount(0); // no remembered price passed off as current
  await expect(card).not.toContainText("1 234");
  await expect(card).not.toContainText(original!);
  answer = "real";
  await card.getByRole("button", { name: "Spróbuj ponownie" }).click();
  await expect(card.getByRole("link")).toHaveCount(1);
  await card.getByRole("button", { name: "Zamknij" }).click();

  answer = "gone";
  await pill.click({ force: true });
  await expect(card).toContainText("nie jest już dostępna");
  await expect(card.getByRole("link")).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Spróbuj ponownie" })).toHaveCount(0);
});

test("paging into a last page with nothing to show keeps focus inside the card", async ({ page }) => {
  test.skip(process.env.E2E_ENGAGEMENT !== "1", "the large same-cell stack comes from the engagement fixtures");
  await page.goto("/wynajem/lublin?widok=mapa");
  await pillRects(page);
  const stack = page.locator('.maplibregl-marker[data-kind="stack"]').first();
  const total = Number((await stack.textContent())?.match(/\d+/)?.[0]);
  expect(total).toBeGreaterThan(10);
  for (const status of [503, 404]) {
    // Reads after the first page are refused; the first page comes from the real API.
    let reads = 0;
    let refuse = true;
    const route = /\/bff\/v1\/classifieds\/[0-9a-f-]{36}$/;
    await page.route(route, async (r) => {
      reads++;
      if (refuse && reads > 10) return r.fulfill({ status, contentType: "application/json", body: "{}" });
      return r.continue();
    });
    await stack.click({ force: true });
    const card = page.getByRole("dialog");
    await expect(card.getByRole("link")).toHaveCount(10);
    let more = card.getByRole("button", { name: /Pokaż kolejne/ });
    while (await more.count()) {
      await more.focus();
      await page.keyboard.press("Enter");
      await page.waitForTimeout(300);
      more = card.getByRole("button", { name: /Pokaż kolejne/ });
    }
    const inCard = await page.evaluate(() => document.activeElement?.closest('[role="dialog"]') !== null);
    expect(inCard, `focus after ${status}`).toBe(true);
    if (status === 503) {
      const retry = card.getByRole("button", { name: "Spróbuj ponownie" });
      await expect(retry).toBeFocused();
      refuse = false;
      await page.keyboard.press("Enter");
      await expect(card.getByRole("link")).toHaveCount(total);
      await expect(card.getByRole("link").nth(10)).toBeFocused();
    } else {
      await expect(card.getByRole("button", { name: "Zamknij" })).toBeFocused();
    }
    await page.keyboard.press("Escape");
    await expect(card).toHaveCount(0);
    await page.unroute(route);
  }
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
  await expect(fresh.getByRole("link", { name: "Wszystkie oferty: Kraków" })).toHaveAttribute("href", "/wynajem/krakow");
  await expect(fresh.getByRole("link", { name: "Wróć do wyników" })).toHaveCount(0);
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
  const listing = page.url().split("/").at(-1)!;
  const origin = new URL(page.url()).origin;
  for (const bad of [
    "https://example.com/wynajem", "//example.com/wynajem", "/wynajem//example.com", "javascript:alert(1)", "/wiadomosci",
    "/wynajem/%2f%2fexample.com", "/wynajem/%252f%252fexample.com", "/wynajem\\..\\oferta", "/wynajem/%5c%5cexample.com",
    "/wynajem/../oferta/1", "/wynajem/%2e%2e/oferta/1", "/wynajem/\uff0fexample.com", "/wynajem/krakow?redirect=https://example.com",
  ]) {
    await page.evaluate(([value, id]) => sessionStorage.setItem("homies.search.listing-origin", JSON.stringify({ listing: id, path: value })), [bad, listing]);
    await page.reload();
    const back = page.getByRole("link", { name: /Wszystkie oferty/ });
    await expect(back, bad).toHaveAttribute("href", "/wynajem/krakow");
    await expect(page.getByRole("link", { name: "Wróć do wyników" }), bad).toHaveCount(0);
  }
  // What the browser and Next's Link actually do with the fallback: same origin, real results.
  await page.getByRole("link", { name: /Wszystkie oferty/ }).click();
  await expect(page).toHaveURL(`${origin}/wynajem/krakow`);
});

test("a listing opened directly never claims the search from another city", async ({ page }) => {
  await page.goto("/wynajem/warszawa");
  const warsaw = page.locator("#wyniki article h3 a").first();
  await expect(warsaw).toBeVisible();
  const krakow = await page.request.get("/bff/v1/geo/localities?country=PL&limit=8&q=Krak%C3%B3w");
  const city = ((await krakow.json()) as { id: string; slug: string; kind: string }[]).find((row) => row.kind === "CITY" && row.slug === "krakow")!;
  const listing = ((await (await page.request.get(`/bff/v1/classifieds?locality_id=${city.id}&limit=1`)).json()) as { items: { id: string }[] }).items[0]!.id;
  await page.goto(`/oferta/${listing}`);
  await expect(page.getByRole("link", { name: "Wróć do wyników" })).toHaveCount(0);
  const back = page.getByRole("link", { name: "Wszystkie oferty: Kraków" });
  await expect(back).toHaveAttribute("href", "/wynajem/krakow");
});

test("a listing's origin belongs to that listing: the search only returns for the one opened from it", async ({ page }) => {
  await page.goto("/wynajem/krakow?koszt_do=6000&sort=najtansze");
  const first = page.locator("#wyniki article h3 a").first();
  await first.click();
  await expect(page).toHaveURL(/\/oferta\//);
  await expect(page.getByRole("link", { name: "Wróć do wyników" })).toHaveAttribute("href", "/wynajem/krakow?koszt_do=6000&sort=najtansze");
  await page.reload();
  await expect(page.getByRole("link", { name: "Wróć do wyników" })).toHaveAttribute("href", "/wynajem/krakow?koszt_do=6000&sort=najtansze");
  await page.getByRole("link", { name: "Wróć do wyników" }).click();
  await expect(page.locator("#sort")).toHaveValue("najtansze");
  // Another listing reached without a card: no claim.
  const other = await page.locator("#wyniki article h3 a").nth(1).getAttribute("href");
  await page.goto(other!);
  await expect(page.getByRole("link", { name: "Wróć do wyników" })).toHaveCount(0);
});

test("opening a listing from the home page offers its city, not an earlier search", async ({ page }) => {
  await page.goto("/wynajem/warszawa");
  await page.locator("#wyniki article").first().waitFor();
  await page.goto("/");
  await page.locator("article h3 a").first().click();
  await expect(page).toHaveURL(/\/oferta\//);
  await expect(page.getByRole("link", { name: "Wróć do wyników" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Wszystkie oferty: Kraków" })).toBeVisible();
});

/** Fixture accounts are only needed for the saved list. */
test("a listing opened from the saved list returns to the saved list", async ({ page, baseURL }) => {
  const unique = crypto.randomUUID();
  const headers = { origin: baseURL!, "x-homies-csrf": "1" };
  expect((await page.request.post("/bff/auth/register", { headers, data: { email: `origin-${unique}@example.com`, password: `Fictional-${unique}!`, full_name: "Tester Powrotu" } })).status()).toBe(200);
  const session = page.waitForResponse((response) => response.url().endsWith("/bff/auth/session"));
  await page.goto("/wynajem/krakow");
  expect(((await (await session).json()) as { authenticated: boolean }).authenticated).toBe(true);
  const firstCard = page.locator("#wyniki article").first();
  await expect(firstCard.getByRole("button", { name: /^Zapisz/ })).toBeEnabled();
  await firstCard.getByRole("button", { name: /^Zapisz/ }).click();
  await expect(firstCard.getByRole("button", { name: /Usuń z zapisanych/ })).toHaveAttribute("aria-pressed", "true");
  await page.goto("/zapisane");
  await page.locator("article h3 a").first().click();
  await expect(page).toHaveURL(/\/oferta\//);
  const back = page.getByRole("link", { name: "Wróć do zapisanych" });
  await expect(back).toHaveAttribute("href", "/zapisane");
  await back.click();
  await expect(page).toHaveURL(/\/zapisane$/);
});

test("the listing's first screen carries the identity, the price and the action", async ({ page }) => {
  await page.goto("/wynajem/krakow?sort=najdrozsze");
  await page.locator("#wyniki article h3 a").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("section").filter({ has: page.getByRole("heading", { name: "Koszty", exact: true }) }).filter({ visible: true })).toHaveCount(1);
  const viewing = page.getByRole("button", { name: "Umów oglądanie" }).filter({ visible: true });
  await expect(viewing).toHaveCount(1);
  const { width, height } = page.viewportSize()!;
  if (width >= 1024) {
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
