import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";

type Account = { email: string; password: string };
type Fixtures = { accounts: Record<"phone_seeker" | "restricted_seeker" | "seeker", Account>; listings: Record<"phone" | "restricted", string> };
type Quota = { remaining: number; used: number; limit: number };
function fixtures(info: TestInfo): Fixtures {
  const path = process.env.E2E_ENGAGEMENT_MANIFEST;
  if (!path || !isAbsolute(path)) throw new Error("Private absolute engagement manifest required");
  const parsed = JSON.parse(readFileSync(path, "utf8")) as { version: number; projects: Record<string, Fixtures> };
  const selected = parsed.projects[info.project.name];
  if (parsed.version !== 1 || !selected?.accounts?.phone_seeker || !selected.listings?.restricted) throw new Error("Unsupported engagement fixture manifest");
  return selected;
}
async function login(page: Page, account: Account) {
  await page.goto("/logowanie");
  await page.getByLabel("E-mail", { exact: true }).fill(account.email);
  await page.getByLabel("Hasło", { exact: true }).fill(account.password);
  await page.locator("form").getByRole("button", { name: "Zaloguj się", exact: true }).last().click();
  await expect(page.getByRole("status").filter({ hasText: "Zalogowano" })).toBeVisible();
}
async function contactDialog(page: Page, listing: string, info: TestInfo): Promise<Locator> {
  const session = page.waitForResponse(response => response.url().endsWith("/bff/auth/session"));
  await page.goto(`/oferta/${listing}`);
  expect((await (await session).json() as { authenticated: boolean }).authenticated).toBe(true);
  if (info.project.name === "mobile") await page.getByRole("button", { name: "Więcej działań", exact: true }).click();
  await page.getByRole("button", { name: "Pokaż numer", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Pokaż numer", exact: true });
  await expect(dialog).toBeVisible(); return dialog;
}
async function quota(page: Page): Promise<Quota> {
  const response = await page.request.get("/bff/v1/me/reveal-quota"); expect(response.status()).toBe(200); return response.json() as Promise<Quota>;
}

async function accessibleDialog(page: Page) {
  const result = await new AxeBuilder({ page }).include("dialog[open]").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  // Do not publish DOM excerpts containing disclosed phone or account information.
  expect(result.violations.map(violation => ({ id: violation.id, impact: violation.impact }))).toEqual([]);
}
// Credentials and disclosed synthetic phone numbers must not enter retained artifacts.
test.use({ trace: "off", screenshot: "off", video: "off" });
test.describe("FE-003d contact disclosure", () => {
  test.skip(process.env.E2E_ENGAGEMENT !== "1", "Requires disposable synthetic engagement fixtures");

  test("real new/repeat reveal charges quota once and clears the phone on blur and navigation", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.phone_seeker);
    const before = await quota(page);
    const dialog = await contactDialog(page, data.listings.phone, info);
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    const reveal = async () => {
      const received = page.waitForResponse(response => response.url().endsWith(`/bff/v1/classifieds/${data.listings.phone}/contact`) && response.request().method() === "POST");
      await dialog.getByRole("button", { name: "Pokaż numer", exact: true }).click();
      const response = await received; expect(response.status()).toBe(200);
      return response.json() as Promise<{ contact_phone: string }>;
    };
    const first = await reveal();
    await expect(dialog.locator('[data-contact-reveal] a')).toHaveAttribute("href", `tel:${first.contact_phone}`);
    await accessibleDialog(page);
    const after = await quota(page); expect(after.used).toBe(before.used + 1); expect(after.remaining).toBe(before.remaining - 1);
    const repeated = await reveal(); expect(repeated.contact_phone).toBe(first.contact_phone);
    const repeatQuota = await quota(page); expect(repeatQuota.used).toBe(after.used); expect(repeatQuota.remaining).toBe(after.remaining);
    await page.evaluate(() => window.dispatchEvent(new Event("blur")));
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    await reveal(); await expect(dialog.locator('[data-contact-reveal] a')).toBeVisible();
    const persisted = await page.evaluate(phone => [localStorage, sessionStorage].some(storage => Array.from({ length: storage.length }, (_, index) => storage.getItem(storage.key(index)!) ?? "").some(value => value.includes(phone))), first.contact_phone);
    expect(persisted).toBe(false);
    await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
    await page.goto("/wiadomosci"); await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText(first.contact_phone);
  });

  test("real prior reveal cannot bypass G-14; exact refusal is409 RECONTACT_BLOCKED, not a CSRF403", async ({ page, baseURL }, info) => {
    const data = fixtures(info); await login(page, data.accounts.restricted_seeker);
    const before = await quota(page);
    const denied = await page.request.post(`/bff/v1/classifieds/${data.listings.restricted}/contact`, { headers: { origin: new URL(baseURL!).origin, "x-homies-csrf": "1" } });
    expect(denied.status()).toBe(409);
    const payload = await denied.json() as Record<string, unknown>;
    expect(typeof payload.detail).toBe("string"); expect(payload.detail).toMatch(/^RECONTACT_BLOCKED:/);
    expect(Object.hasOwn(payload, "contact_phone")).toBe(false);
    expect(/\+\d{7,15}/.test(JSON.stringify(payload))).toBe(false);
    expect((await quota(page)).used).toBe(before.used);
  });

  test("real unverified seeker sees verification form without issuing a reveal or verifying the seed account", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.seeker);
    const writes: string[] = [];
    page.on("request", request => { if (request.method() === "POST" && /\/contact$|\/verify\/phone\//.test(request.url())) writes.push(new URL(request.url()).pathname); });
    const dialog = await contactDialog(page, data.listings.phone, info);
    await expect(dialog.getByRole("heading", { name: "Potwierdź numer telefonu", exact: true })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Wyślij kod", exact: true })).toBeVisible();
    await accessibleDialog(page);
    expect(writes).toEqual([]); await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    const state = await (await page.request.get("/bff/auth/session")).json() as { user: { phoneVerified: boolean } }; expect(state.user.phoneVerified).toBe(false);
  });

  test("MOCKED verification success requires a deliberate second reveal press; no real SMS or account verification", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.seeker);
    let verified = false; let disclosureCount = 0;
    await page.route("**/bff/auth/session", async route => { const actual = await route.fetch(); const state = await actual.json() as { user?: { phoneVerified: boolean } }; if (state.user) state.user.phoneVerified = verified; await route.fulfill({ response: actual, json: state }); });
    await page.route("**/bff/v1/me/verify/phone/start", route => route.fulfill({ status: 202, contentType: "application/json", body: "{}" }));
    await page.route("**/bff/v1/me/verify/phone/confirm", async route => { verified = true; await route.fulfill({ status: 204 }); });
    await page.route(`**/bff/v1/classifieds/${data.listings.phone}/contact`, async route => { disclosureCount++; await route.fulfill({ status: 200, json: { offer_id: data.listings.phone, contact_phone: "+48123456789" } }); });
    const dialog = await contactDialog(page, data.listings.phone, info);
    await dialog.getByLabel("Numer telefonu (np. +48123456789)", { exact: true }).fill("+48123456789");
    await dialog.getByRole("button", { name: "Wyślij kod", exact: true }).click();
    await dialog.getByLabel("Kod potwierdzenia", { exact: true }).fill("123456");
    await dialog.getByRole("button", { name: "Potwierdź kod", exact: true }).click();
    await expect(dialog.getByText("Numer potwierdzony. Naciśnij ponownie „Pokaż numer”.", { exact: true })).toBeVisible();
    expect(disclosureCount).toBe(0); await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    await dialog.getByRole("button", { name: "Wstecz", exact: true }).click();
    expect(disclosureCount).toBe(0);
    await dialog.getByRole("button", { name: "Pokaż numer", exact: true }).click();
    await expect(dialog.locator('[data-contact-reveal] a')).toHaveAttribute("href", "tel:+48123456789"); expect(disclosureCount).toBe(1);
  });

  test("MOCKED delayed reveal response cannot redisclose a phone after blur", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.phone_seeker);
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    let began!: () => void;
    const started = new Promise<void>(resolve => { began = resolve; });
    await page.route(`**/bff/v1/classifieds/${data.listings.phone}/contact`, async route => {
      began(); await gate;
      await route.fulfill({ status: 200, json: { offer_id: data.listings.phone, contact_phone: "+48123456789" } });
    });
    const dialog = await contactDialog(page, data.listings.phone, info);
    const button = dialog.getByRole("button", { name: "Pokaż numer", exact: true });
    await button.click(); await started;
    await page.evaluate(() => window.dispatchEvent(new Event("blur")));
    release();
    // Wait for the pending response to be processed, not merely an initial empty DOM.
    await expect(button).toHaveAttribute("aria-busy", "false");
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
  });
  for (const previouslyDisclosed of [false, true]) {
    test(`MOCKED ${previouslyDisclosed ? "repeat" : "new"} reveal refusal clears every phone surface and disables engagement`, async ({ page }, info) => {
      const data = fixtures(info); await login(page, data.accounts.phone_seeker);
      let calls = 0;
      // The real restricted listing can be nonpublic. Exercise rendering on an
      // accessible phone fixture; the separate unmocked test proves the backend gate.
      await page.route(`**/bff/v1/classifieds/${data.listings.phone}/contact`, async route => {
        calls++;
        if (previouslyDisclosed && calls === 1) await route.fulfill({ status: 200, json: { offer_id: data.listings.phone, contact_phone: "+48123456789" } });
        else await route.fulfill({ status: 409, json: { detail: "RECONTACT_BLOCKED: private moderation reason" } });
      });
      const dialog = await contactDialog(page, data.listings.phone, info);
      if (previouslyDisclosed) { await dialog.getByRole("button", { name: "Pokaż numer", exact: true }).click(); await expect(dialog.locator('[data-contact-reveal] a')).toBeVisible(); }
      await dialog.getByRole("button", { name: "Pokaż numer", exact: true }).click();
      await expect(dialog.getByText("Nie możesz zobaczyć numeru do tej oferty", { exact: true })).toBeVisible();
      await expect(page.locator('a[href^="tel:"]')).toHaveCount(0); await expect(page.locator("body")).not.toContainText("private moderation reason");
      await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
      await expect(page.getByRole("button", { name: "Umów oglądanie", exact: true })).toBeDisabled();
      if (info.project.name === "mobile") await page.getByRole("button", { name: "Więcej działań", exact: true }).click();
      await expect(page.getByRole("button", { name: "Pokaż numer", exact: true })).toBeDisabled();
      await expect(page.getByRole("button", { name: "Napisz", exact: true })).toBeDisabled();
    });
  }
});
