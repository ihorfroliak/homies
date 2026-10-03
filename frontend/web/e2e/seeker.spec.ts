import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * FE-002 seeker slice against the real backend with the E2E seed
 * (backend/app/scripts/seed_e2e.py: 10 Kraków + 2 Warszawa fictional
 * listings). Skipped unless E2E_BACKEND=1.
 */
test.skip(process.env.E2E_BACKEND !== "1", "needs the API with the E2E seed");

const norm = (s: string | null) => (s ?? "").replace(/[  ]/g, " ");
const money = (s: string) => Number(norm(s).replace(/[^\d]/g, ""));

async function prices(page: Page): Promise<number[]> {
  return (await page.locator("#wyniki article p:first-of-type").allTextContents()).map(money);
}


type Ev = { event_name: string; route: string; props: Record<string, unknown> };
/** Events in the E2E memory sink; null until the analytics instance exists. */
function sinkEvents(page: Page): Promise<Ev[] | null> {
  return page.evaluate(() => (window as unknown as { __homies?: { sink: { events: Ev[] } } }).__homies?.sink.events ?? null);
}

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

test("home: newest Kraków rail from the API and the search box", async ({ page }) => {
  await page.goto("/");
  const rail = page.getByRole("region", { name: "Najnowsze w Krakowie" });
  await expect(rail.getByRole("article")).toHaveCount(6);
  await page.getByLabel("Miasto").fill("Kraków");
  await page.getByLabel("Maks. koszt miesięczny (zł)").fill("4000");
  await page.getByRole("button", { name: "Szukaj" }).click();
  await expect(page).toHaveURL(/\/wynajem\/krakow\?koszt_do=4000$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Mieszkania na wynajem — Kraków");
});

test("results: count, cards, canonical sort, and pagination-free small sets", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  await expect(page.getByText("Znaleźliśmy 10 ofert")).toBeVisible();
  await expect(page.locator("#wyniki article")).toHaveCount(10);
  const first = page.locator("#wyniki article").first();
  await expect(first).toContainText("zł / mies.");
  await expect(first).toContainText("Na start");
  await page.getByLabel("Sortuj").selectOption({ label: "Najniższy koszt miesięczny" });
  await expect(page).toHaveURL(/sort=najtansze/);
  const sorted = await prices(page);
  expect(sorted).toEqual([...sorted].sort((a, b) => a - b));
  await axe(page);
});

test("area page, filters from the URL, chips and their removal", async ({ page }) => {
  await page.goto("/wynajem/krakow/kazimierz");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Mieszkania na wynajem — Kazimierz, Kraków");
  await expect(page.getByText("Znaleźliśmy 3 oferty")).toBeVisible();
  await page.goto("/wynajem/krakow?pokoje_od=3");
  await expect(page.getByText("Znaleźliśmy 3 oferty")).toBeVisible();
  await expect(page.getByRole("button", { name: "Filtry (1)" }).or(page.getByText("Filtry (1)"))).toBeVisible();
  await page.getByRole("link", { name: "Usuń filtr: Pokoje od 3" }).click();
  await expect(page).toHaveURL(/\/wynajem\/krakow$/);
  await expect(page.getByText("Znaleźliśmy 10 ofert")).toBeVisible();
});

test("live count on the filter form, then submit", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  await page.getByText("Filtry", { exact: true }).click();
  await page.getByLabel("Pokoje (od)").fill("4");
  await expect(page.getByRole("button", { name: "Pokaż 1 oferta" })).toBeVisible();
  await page.getByRole("button", { name: "Pokaż 1 oferta" }).click();
  await expect(page).toHaveURL(/\/wynajem\/krakow\?pokoje_od=4$/);
  await expect(page.locator("#wyniki article")).toHaveCount(1);
});

test("zero results offer real relaxations; bad parameters are dropped, not fatal", async ({ page }) => {
  await page.goto("/wynajem/krakow?koszt_do=1&winda=tak");
  await expect(page.getByRole("heading", { name: "Brak ofert dla tych filtrów" })).toBeVisible();
  const relax = page.getByRole("link", { name: /^Usuń »Koszt do 1\szł« → \d+\s?ofert/ });
  await expect(relax).toBeVisible();
  await page.goto("/wynajem/krakow?pokoje_od=abc&nieznany=1");
  await expect(page.getByText("Pominęliśmy nieprawidłowy filtr w adresie.")).toBeVisible();
  await expect(page.getByText("Znaleźliśmy 10 ofert")).toBeVisible();
});

test("unknown places and listings are 404, never 410", async ({ page }) => {
  for (const path of ["/wynajem/atlantyda", "/wynajem/krakow/nie-ma-takiej", "/wynajem/a/b/c", "/oferta/00000000-0000-4000-8000-000000000000", "/oferta/..%2Fadmin"]) {
    const response = await page.goto(path);
    expect(response!.status(), path).toBe(404);
  }
});

test("listing detail: costs, facts, freshness wording, privacy note", async ({ page }) => {
  await page.goto("/wynajem/krakow?sort=najdrozsze");
  const link = page.locator("#wyniki article h3 a").first();
  const title = await link.textContent();
  await link.click();
  await expect(page).toHaveURL(/\/oferta\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(title!);
  const costs = page.getByRole("complementary");
  await expect(costs.getByText("Koszt miesięczny", { exact: true })).toBeVisible();
  await expect(costs.getByText("Czynsz administracyjny")).toBeVisible();
  await expect(costs.getByText("Kaucja (zwrotna)")).toBeVisible();
  await expect(page.getByText("Pokoje", { exact: true })).toBeVisible();
  await expect(page.getByText(/Potwierdzona jako aktualna/)).toBeVisible();
  await expect(page.getByText("Lokalizacja przybliżona — dokładny adres zna tylko właściciel.")).toBeVisible();
  const html = await page.content();
  expect(html).not.toMatch(/ul\. (Fikcyjna|Testowa|Wzorcowa|Robocza)/); // the street never reaches the public page
  expect(await page.locator('meta[name="robots"]').getAttribute("content")).toContain("noindex");
  await axe(page);
});

test("map mode: price pills, stacks, map card, and no tile server", async ({ page }) => {
  const tileRequests: string[] = [];
  page.on("request", (r) => {
    if (/tile|openstreetmap|demotiles/.test(r.url())) tileRequests.push(r.url());
  });
  await page.goto("/wynajem/krakow?widok=mapa");
  const map = page.getByRole("region", { name: /Mapa ofert/ }).last();
  await expect(map).toBeVisible();
  await expect(page.locator(".maplibregl-marker")).not.toHaveCount(0);
  await page.locator(".maplibregl-marker").first().click();
  const card = page.getByRole("dialog");
  await expect(card.getByRole("link").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
  expect(tileRequests).toEqual([]);
  await expect(page.getByText(/ma podaną tylko dzielnicę/)).toBeVisible(); // the seeded DISTRICT-only room
});

test("analytics: nothing without consent; with consent a search is one clean event", async ({ page }) => {
  await page.goto("/wynajem/krakow");
  // The tracker mounted (the instance exists) and still recorded nothing.
  await expect.poll(async () => (await sinkEvents(page))?.length ?? -1).toBe(0);
  await page.waitForTimeout(300);
  expect(await sinkEvents(page)).toEqual([]);

  await page.addInitScript(() => {
    (window as unknown as { __homiesConsentPreset: string[] }).__homiesConsentPreset = ["ANALYTICS_FIRST_PARTY"];
  });
  await page.goto("/wynajem/krakow?pokoje_od=2");
  await expect.poll(async () => ((await sinkEvents(page)) ?? []).map((e) => e.event_name)).toContain("search_performed");
  const events = (await sinkEvents(page)) ?? [];
  const search = events.find((e) => e.event_name === "search_performed")!;
  expect(search.route).toBe("/wynajem/[miasto]");
  expect(search.props.result_count).toBeGreaterThan(0);
  expect(search.props.filter_dimensions).toEqual(expect.arrayContaining(["locality_id", "min_rooms"]));
  expect(JSON.stringify(events)).not.toMatch(/user_id|krakow\?|@/);
  await page.locator("#wyniki article h3 a").first().click();
  await expect.poll(async () => ((await sinkEvents(page)) ?? []).map((e) => e.event_name)).toContain("listing_viewed");
  const viewed = ((await sinkEvents(page)) ?? []).find((e) => e.event_name === "listing_viewed")!;
  expect(viewed.props.search_id).toBe(search.props.search_id);
  expect(viewed.props.position).toBe(1);
});

test("list mode never loads the map library", async ({ page }) => {
  await page.goto("/wynajem/krakow", { waitUntil: "load" });
  await page.waitForTimeout(800);
  const scripts = await page.evaluate(() => performance.getEntriesByType("resource").map((e) => e.name));
  expect(scripts.some((u) => /maplibre/i.test(u))).toBe(false);
  expect(await page.locator(".maplibregl-map").count()).toBe(0);
});
