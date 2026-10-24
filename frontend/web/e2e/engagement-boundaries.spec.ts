import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type TestInfo } from "@playwright/test";
import { INTENT_KEY } from "../src/engagement/intent";
type Fixture = { accounts: Record<"provider" | "seeker", { email: string; password: string }>; listings: { approval: string }; conversations: { approval: string }; messages: { reportable: string } };
function fixture(info: TestInfo): Fixture {
  const file = process.env.E2E_ENGAGEMENT_MANIFEST;
  if (!file || !isAbsolute(file)) throw new Error("Private absolute fixture manifest required");
  const manifest = JSON.parse(readFileSync(file, "utf8")) as { version: number; projects: Record<string, Fixture> };
  if (manifest.version !== 1 || !manifest.projects[info.project.name]) throw new Error("Unsupported fixture manifest");
  return manifest.projects[info.project.name]!;
}
test.use({ trace: "off", screenshot: "off", video: "off" });
test.skip(process.env.E2E_ENGAGEMENT !== "1", "Requires disposable engagement fixtures");

test("restored report intent rechecks the authorized thread and opens an empty form without sending", async ({ page, baseURL }, info) => {
  const f = fixture(info);
  expect((await page.request.post("/bff/auth/login", { headers: { origin: baseURL!, "x-homies-csrf": "1" }, data: f.accounts.seeker })).status()).toBe(200);
  await page.goto("/logowanie");
  await page.evaluate(({ key, message }) => sessionStorage.setItem(key, JSON.stringify({ action: "report", message_id: message, initiator_id: "engagement-status", created_at: Date.now() })), { key: INTENT_KEY, message: f.messages.reportable });
  let reports = 0; page.on("request", request => { if (request.url().endsWith("/bff/v1/reports") && request.method() === "POST") reports++; });
  await page.goto(`/wiadomosci/${f.conversations.approval}`);
  const dialog = page.getByRole("dialog", { name: "Zgłoś wiadomość", exact: true });
  await expect(dialog).toBeVisible(); await expect(dialog.getByLabel("Dodatkowe informacje (opcjonalnie)", { exact: true })).toHaveValue("");
  expect(reports).toBe(0); expect(await page.evaluate(key => sessionStorage.getItem(key), INTENT_KEY)).toBeNull();
  await dialog.getByRole("button", { name: "Zamknij", exact: true }).click(); expect(reports).toBe(0);
});

test("auth sheet traps keyboard focus, Escape abandons intent and restores the initiator", async ({ page }, info) => {
  await page.goto(`/oferta/${fixture(info).listings.approval}`);
  const opener = page.getByRole("button", { name: /^Zapisz:/ }).filter({ visible: true });
  await opener.click();
  const dialog = page.getByRole("dialog"); await expect(dialog.getByLabel("E-mail", { exact: true })).toBeFocused();
  const focusables = dialog.locator("button, input, a[href], textarea, select").filter({ visible: true });
  await focusables.last().focus(); await page.keyboard.press("Tab"); await expect(focusables.first()).toBeFocused();
  await page.keyboard.press("Shift+Tab"); await expect(focusables.last()).toBeFocused();
  await page.keyboard.press("Escape"); await expect(dialog).toHaveCount(0); await expect(opener).toBeFocused();
  expect(await page.evaluate(() => Object.values(sessionStorage).some(value => value.includes('"action":"save"')))).toBe(false);
});

for (const cancel of [false, true]) {
  test(`provider ${cancel ? "confirms then cancels" : "declines"} a fresh real viewing and requester sees the response state`, async ({ page, baseURL }, info) => {
    const f = fixture(info); const nonce = randomUUID(); const account = { email: `boundary-${nonce}@example.com`, password: `Fictional-${nonce}!` };
    const headers = { origin: baseURL!, "x-homies-csrf": "1" };
    expect((await page.request.post("/bff/auth/register", { headers, data: { ...account, full_name: "Próba Granic" } })).status()).toBe(200);
    const available = await page.request.get(`/bff/v1/classifieds/${f.listings.approval}/viewing-slots?days=14`);
    expect(available.status()).toBe(200);
    const slots = (await available.json() as { slots: string[] }).slots;
    expect(slots.length).toBeGreaterThan(3);
    const note = `Syntetyczna granica ${nonce}`;
    const created = await page.request.post(`/bff/v1/classifieds/${f.listings.approval}/viewings`, { headers, data: { starts_at: slots[cancel ? 2 : 3], attendee_count: 1, note } });
    expect(created.status()).toBe(201); const viewing = await created.json() as { id: string; status: string }; expect(viewing.status).toBe("REQUESTED");
    expect((await page.request.post("/bff/auth/logout", { headers })).ok()).toBe(true);
    expect((await page.request.post("/bff/auth/login", { headers, data: f.accounts.provider })).status()).toBe(200);
    await page.goto("/panel/ogladania");
    const row = page.locator("article").filter({ hasText: note }); await expect(row).toHaveCount(1);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations.map(value => ({ id: value.id, impact: value.impact }))).toEqual([]);
    if (cancel) {
      await row.getByRole("button", { name: /^Potwierdź:/ }).click(); await expect(row.getByRole("status")).toContainText("Oglądanie potwierdzone");
      await row.getByRole("button", { name: /^Odwołaj oglądanie:/ }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Odwołaj oglądanie", exact: true }).click();
    } else await row.getByRole("button", { name: /^Odrzuć:/ }).click();
    const expected = cancel ? "CANCELLED" : "DECLINED";
    await expect.poll(async () => {
      const read = await page.request.get(`/bff/v1/classifieds/${f.listings.approval}/viewings`);
      return ((await read.json()) as { id: string; status: string }[]).find(item => item.id === viewing.id)?.status;
    }).toBe(expected);
    expect((await page.request.post("/bff/auth/logout", { headers })).ok()).toBe(true);
    expect((await page.request.post("/bff/auth/login", { headers, data: account })).status()).toBe(200);
    await page.goto("/ogladania");
    await expect(page.locator("article").getByRole("status")).toContainText(cancel ? "Oglądanie odwołane" : "Właściciel nie przyjął tego terminu");
    await expect(page.locator("main")).not.toContainText("PROVIDER");
  });
}
