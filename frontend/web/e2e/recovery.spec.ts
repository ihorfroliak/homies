import { spawn, type ChildProcess } from "node:child_process";
import { createServer, request as httpRequest, type Server } from "node:http";
import { expect, test, type Page } from "@playwright/test";

/**
 * FE-UX-KRK-002R UX-R6: recovery after a temporary backend failure, end to end. The
 * web server runs against a small fault proxy in front of the real API, so failures
 * are real server-side responses and "recovered" means the real API answered.
 */
test.skip(process.env.E2E_BACKEND !== "1", "needs the API with the E2E seed");
test.describe.configure({ mode: "serial" });

const UPSTREAM = new URL(process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000");
const SECRET = "internal-detail-must-not-reach-the-page";
type Fault = { match: RegExp; mode: "503" | "429" | "404" | "hang" | "slow" } | null;
let fault: Fault = null;
const seen: string[] = [];
let proxy: Server;
let web: ChildProcess;
let base: string;
let listingId: string;

test.beforeAll(async ({}, info) => {
  test.setTimeout(90_000);
  const proxyPort = 3400 + info.parallelIndex * 2 + (info.project.name === "mobile" ? 40 : 0);
  const webPort = proxyPort + 1;
  base = `http://localhost:${webPort}`;
  proxy = createServer((req, res) => {
    const path = req.url ?? "/";
    seen.push(path);
    const active = fault && fault.match.test(path) ? fault.mode : null;
    if (active === "hang") return; // the web server's own deadline must end this
    if (active === "503" || active === "429" || active === "404") {
      res.writeHead(Number(active), { "content-type": "application/json", ...(active === "429" ? { "retry-after": "1" } : {}) });
      res.end(JSON.stringify({ detail: SECRET }));
      return;
    }
    const forward = () => {
      const upstream = httpRequest({ host: UPSTREAM.hostname, port: UPSTREAM.port, path, method: req.method, headers: req.headers }, (answer) => {
        res.writeHead(answer.statusCode ?? 502, answer.headers);
        answer.pipe(res);
      });
      upstream.on("error", () => res.destroy());
      req.pipe(upstream);
    };
    if (active === "slow") setTimeout(forward, 1200);
    else forward();
  });
  await new Promise<void>((resolve) => proxy.listen(proxyPort, "127.0.0.1", resolve));
  web = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "-p", String(webPort), "-H", "127.0.0.1"], {
    cwd: process.cwd(),
    stdio: "ignore",
    env: { ...process.env, API_INTERNAL_URL: `http://127.0.0.1:${proxyPort}`, API_TIMEOUT_MS: "1500", PUBLIC_ORIGIN: base, HOMIES_WEB_ENV: "development" },
  });
  for (let i = 0; i < 60; i++) {
    const up = await fetch(`${base}/healthz`).then((r) => r.ok).catch(() => false);
    if (up) break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  const page = (await (await fetch(`http://${UPSTREAM.host}/v1/classifieds?limit=1&country_code=PL`)).json()) as { items: { id: string }[] };
  listingId = page.items[0]!.id;
});

test.afterAll(async () => {
  fault = null;
  web?.kill();
  await new Promise((resolve) => proxy?.close(resolve));
});

test.beforeEach(() => {
  fault = null;
});

const retry = (page: Page) => page.getByRole("link", { name: "Spróbuj ponownie" }).or(page.getByRole("button", { name: "Spróbuj ponownie" })).first();

async function noLeak(page: Page) {
  expect(await page.locator("body").textContent()).not.toContain(SECRET);
}

for (const [name, mode] of [["503", "503"], ["429", "429"], ["a timeout", "hang"]] as const) {
  test(`results recover after ${name} and keep the filters`, async ({ page }) => {
    await page.goto(`${base}/wynajem/krakow?pokoje_od=2`); // resolves the place while the API is healthy
    fault = { match: /^\/v1\/classifieds/, mode };
    const failed = await page.goto(`${base}/wynajem/krakow?pokoje_od=3`);
    expect(failed!.status()).toBe(200); // the page itself rendered; the failure is an inline state
    const alert = page.getByRole("alert").filter({ hasText: "Spróbuj ponownie" });
    await expect(alert).toBeVisible();
    await expect(page.locator("#wyniki article")).toHaveCount(0);
    await noLeak(page);
    fault = null;
    await retry(page).click();
    await expect(page).toHaveURL(/pokoje_od=3$/);
    await expect(page.locator("#wyniki article")).toHaveCount(3);
    await expect(page.getByRole("alert").filter({ hasText: "Spróbuj ponownie" })).toHaveCount(0);
  });

  test(`a listing recovers after ${name}`, async ({ page }) => {
    fault = { match: /^\/v1\/classifieds\/[^/?]+$/, mode };
    await page.goto(`${base}/oferta/${listingId}`);
    await expect(page.getByRole("alert").filter({ hasText: "Spróbuj ponownie" })).toBeVisible();
    await noLeak(page);
    fault = null;
    await retry(page).click();
    await expect(page.getByRole("button", { name: "Umów oglądanie" }).filter({ visible: true })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).not.toHaveText("Coś poszło nie tak");
  });
}

test("a place the server could not resolve recovers through the error boundary, also after repeated retries", async ({ page }) => {
  fault = { match: /^\/v1\/geo\/localities\/by-slug/, mode: "503" };
  const failed = await page.goto(`${base}/wynajem/warszawa`);
  expect(failed!.status()).toBe(500);
  const alert = page.getByRole("alert").filter({ hasText: "Coś poszło nie tak" });
  await expect(alert).toBeVisible();
  await noLeak(page);
  // Each retry must ask the server again, not re-render the same failure.
  for (let attempt = 0; attempt < 2; attempt++) {
    const before = seen.length;
    await retry(page).click();
    await expect.poll(() => seen.slice(before).some((p) => p.startsWith("/v1/geo/localities/by-slug"))).toBe(true);
    await expect(alert).toBeVisible();
    await expect(retry(page)).toBeEnabled();
  }
  fault = null;
  await retry(page).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Warszawa");
  await expect(page.locator("#wyniki article")).not.toHaveCount(0);
  await expect(alert).toHaveCount(0);
});

test("retry while a retry is pending does not stack requests", async ({ page }) => {
  fault = { match: /^\/v1\/geo\/localities\/by-slug/, mode: "503" };
  await page.goto(`${base}/wynajem/gdansk`).catch(() => undefined);
  const button = retry(page);
  await expect(button).toBeVisible();
  fault = { match: /^\/v1\/geo\/localities\/by-slug/, mode: "slow" };
  const before = seen.length;
  await button.click();
  await expect(button).toBeDisabled();
  await button.click({ force: true }).catch(() => undefined);
  await expect.poll(() => seen.length).toBeGreaterThan(before);
  await page.waitForTimeout(2000);
  expect(seen.slice(before).filter((p) => p.startsWith("/v1/geo/localities/by-slug")).length).toBeLessThanOrEqual(1);
});

test("a listing the API does not have stays a 404, with no retry pretending otherwise", async ({ page }) => {
  fault = { match: /^\/v1\/classifieds\/[^/?]+$/, mode: "404" };
  const response = await page.goto(`${base}/oferta/${listingId}`);
  expect(response!.status()).toBe(404);
  await noLeak(page);
  await expect(page.getByRole("button", { name: "Umów oglądanie" })).toHaveCount(0);
});
