import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/** FE-001 foundation: shell, security headers, BFF guards, accessibility. No backend needed. */

test("home renders the Polish shell with a working skip link", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "pl");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Przejdź do treści" });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("main#tresc")).toBeFocused();
});

test("pages carry the nonce CSP, security headers and the noindex kill switch", async ({ page }) => {
  const response = await page.goto("/");
  const headers = response!.headers();
  const csp = headers["content-security-policy"] ?? "";
  expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(csp).toContain("frame-ancestors 'none'");
  expect(headers["x-robots-tag"]).toBe("noindex, nofollow");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-request-id"]).toMatch(/^[A-Za-z0-9._-]{8,64}$/);
  expect(headers["x-powered-by"]).toBeUndefined();
  // Every script Next.js rendered carries this request's nonce, so the page runs under CSP.
  const nonce = /'nonce-([^']+)'/.exec(csp)![1];
  const scripts = await page.locator("script").evaluateAll((els) => els.map((e) => (e as HTMLScriptElement).nonce));
  expect(scripts.length).toBeGreaterThan(0);
  for (const value of scripts) expect(value).toBe(nonce);
  const meta = await page.locator('meta[name="robots"]').getAttribute("content");
  expect(meta).toContain("noindex");
});

test("no CSP violation and no console error on load", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(m.text());
  });
  page.on("pageerror", (e) => problems.push(e.message));
  await page.goto("/", { waitUntil: "load" });
  await page.waitForTimeout(1500);
  expect(problems).toEqual([]);
});

test("unknown pages answer 404 with a way forward", async ({ page }) => {
  const response = await page.goto("/to-nie-istnieje");
  expect(response!.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Nie znaleźliśmy tej strony" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Przejdź do wyszukiwania" })).toHaveAttribute("href", "/wynajem");
});

test("BFF refuses cross-site writes and unknown routes", async ({ request, baseURL }) => {
  const crossSite = await request.post("/bff/auth/logout", { headers: { origin: "https://evil.example" } });
  expect(crossSite.status()).toBe(403);
  const noHeader = await request.post("/bff/auth/logout", { headers: { origin: baseURL! } });
  expect(noHeader.status()).toBe(403);
  const ok = await request.post("/bff/auth/logout", { headers: { origin: baseURL!, "x-homies-csrf": "1" } });
  expect(ok.status()).toBe(200);
  expect(ok.headers()["set-cookie"] ?? "").toContain("__Host-hm_at=;");
  expect((await request.get("/bff/v1/admin/moderation/queue")).status()).toBe(404);
  // An encoded separator must not smuggle a path past the allowlist.
  expect((await request.get("/bff/v1/classifieds%2F..%2Fadmin")).status()).toBe(404);
  expect((await request.post("/bff/v1/classifieds", { headers: { origin: baseURL!, "x-homies-csrf": "1" } })).status()).toBe(404);
});

test("anonymous session is reported without calling the backend", async ({ request }) => {
  const response = await request.get("/bff/auth/session");
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ authenticated: false });
  expect(response.headers()["cache-control"]).toContain("no-store");
});

test("robots.txt allows crawling but keeps private surfaces out", async ({ request }) => {
  const body = await (await request.get("/robots.txt")).text();
  expect(body).toContain("Allow: /");
  expect(body).toContain("Disallow: /bff/");
});

for (const path of ["/", "/to-nie-istnieje"]) {
  test(`axe: no WCAG 2.2 AA violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
}
