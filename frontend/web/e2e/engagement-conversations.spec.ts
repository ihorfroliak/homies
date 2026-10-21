import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** Real API, disposable synthetic fixtures only. Never attach the private manifest. */
type Account = { email: string; password: string };
type Fixtures = {
  accounts: Record<"seeker" | "provider" | "guest_provider" | "unverified_provider" | "host_without_authority" | "restricted_seeker", Account>;
  listings: Record<"instant" | "approval" | "unverified", string>;
  conversations: Record<"approval" | "closed" | "redacted" | "restricted" | "unverified", string>;
  messages: { reportable: string };
};
type Detail = { conversation: { id: string; status: string; my_side: string }; messages: { id: string; body: string | null; moderation_state: string }[] };
function fixtures(info: TestInfo): Fixtures {
  const file = process.env.E2E_ENGAGEMENT_MANIFEST;
  if (!file || !isAbsolute(file)) throw new Error("A private absolute E2E_ENGAGEMENT_MANIFEST is required");
  const value = JSON.parse(readFileSync(file, "utf8")) as { version: number; projects: Record<string, Fixtures> };
  const result = value.projects[info.project.name];
  if (value.version !== 1 || !result?.accounts?.seeker || !result.conversations?.approval || !result.messages?.reportable) throw new Error("Unsupported or incomplete engagement fixture manifest");
  return result;
}
async function login(page: Page, account: Account) {
  await page.goto("/logowanie");
  await page.getByLabel("E-mail", { exact: true }).fill(account.email);
  await page.getByLabel("Hasło", { exact: true }).fill(account.password);
  await page.locator("form").getByRole("button", { name: "Zaloguj się", exact: true }).last().click();
  await expect(page.getByRole("status").filter({ hasText: "Zalogowano" })).toBeVisible();
}
async function readThread(page: Page, id: string): Promise<Detail> {
  const result = await page.request.get(`/bff/v1/conversations/${id}`);
  expect(result.status()).toBe(200);
  return result.json() as Promise<Detail>;
}

// Authentication and message/report contents stay out of retained traces/artifacts.
test.use({ trace: "off", screenshot: "off", video: "off" });
test.describe("FE-003c real conversations", () => {
  test.skip(process.env.E2E_ENGAGEMENT !== "1", "Requires the disposable FE-003 engagement fixtures");


  test("seeded requester inbox opens real messages; closed and redacted states remain private", async ({ page }, info) => {
    const data = fixtures(info);
    await login(page, data.accounts.seeker);
    await page.goto("/wiadomosci");
    await expect(page.getByRole("heading", { level: 1, name: "Wiadomości" })).toBeVisible();
    await expect(page.locator(`a[href='/wiadomosci/${data.conversations.approval}']`)).toBeVisible();
    await page.locator(`a[href='/wiadomosci/${data.conversations.approval}']`).click();
    await expect(page.getByRole("log")).toBeVisible();
    await expect(page.getByLabel("Wiadomość", { exact: true })).toBeEditable();
    expect((await new AxeBuilder({ page }).analyze()).violations.map(item => ({ id: item.id, impact: item.impact }))).toEqual([]);
    await page.goto(`/wiadomosci/${data.conversations.closed}`);
    await expect(page.getByRole("log")).toBeVisible();
    await expect(page.getByText("Homies zamknął tę rozmowę", { exact: true }).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByLabel("Wiadomość", { exact: true })).toHaveCount(0);
    await page.goto(`/wiadomosci/${data.conversations.redacted}`);
    await expect(page.getByRole("log").getByText("Wiadomość usunięta przez Homies", { exact: true })).toBeVisible();
    const redacted = await readThread(page, data.conversations.redacted);
    const removed = redacted.messages.filter(item => item.moderation_state === "REMOVED");
    expect(removed.length).toBeGreaterThan(0);
    expect(removed.every(item => item.body === null)).toBe(true);
    await expect(page.getByRole("log").getByRole("button", { name: "Zgłoś wiadomość", exact: true })).toHaveCount(0);
  });

  test("unverified requester reports the other participant without a contact-verification wall", async ({ page }, info) => {
    const data = fixtures(info);
    await login(page, data.accounts.seeker);
    const session = await page.request.get("/bff/auth/session");
    expect(session.status()).toBe(200);
    const state = await session.json() as { user: { phoneVerified: boolean; emailVerified: boolean } };
    expect(state.user.phoneVerified).toBe(false); expect(state.user.emailVerified).toBe(false);
    await page.goto(`/wiadomosci/${data.conversations.approval}`);
    await page.getByRole("log").getByRole("button", { name: "Zgłoś wiadomość", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Zgłoś wiadomość", exact: true });
    await expect(dialog).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations.map(item => ({ id: item.id, impact: item.impact }))).toEqual([]);
    const reportResult = page.waitForResponse(response => response.url().endsWith("/bff/v1/reports") && response.request().method() === "POST");
    await dialog.getByRole("button", { name: "Wyślij zgłoszenie", exact: true }).click();
    const first = await reportResult;
    expect(first.status()).toBe(201);
    const posted = first.request().postDataJSON() as { target_type: string; target_id: string; reason: string };
    expect(posted.target_type).toBe("MESSAGE"); expect(posted.target_id).toBe(data.messages.reportable);
    await expect(dialog.getByText("Zgłoszenie przyjęte", { exact: true })).toBeVisible();
    await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
    await page.getByRole("log").getByRole("button", { name: "Zgłoś wiadomość", exact: true }).click();
    const repeatedResult = page.waitForResponse(response => response.url().endsWith("/bff/v1/reports") && response.request().method() === "POST");
    await page.getByRole("dialog").getByRole("button", { name: "Wyślij zgłoszenie", exact: true }).click();
    expect((await repeatedResult).status()).toBe(200);
    await expect(page.getByRole("dialog").getByText("Zgłoszenie przyjęte", { exact: true })).toBeVisible();
  });

  for (const account of ["provider", "guest_provider"] as const) {
    test(`${account} enters provider messages through current authority, independently of role`, async ({ page }, info) => {
      const data = fixtures(info);
      await login(page, data.accounts[account]);
      const enumeration = await page.request.get("/bff/v1/me/classifieds?scope=MANAGE_MESSAGES");
      expect(enumeration.status()).toBe(200);
      const ids = (await enumeration.json() as { id: string }[]).map(row => row.id);
      expect(ids).toContain(data.listings.approval);
      await page.goto(`/panel/leady/${data.conversations.approval}`);
      await expect(page.getByRole("log")).toBeVisible();
      await expect(page.getByLabel("Wiadomość", { exact: true })).toBeEditable();
      expect((await readThread(page, data.conversations.approval)).conversation.my_side).toBe("provider");
      await expect(page.getByRole("log")).not.toContainText(data.accounts.seeker.email);
    });
  }

  for (const account of ["unverified_provider", "host_without_authority"] as const) {
    test(`${account} cannot expose provider inbox or a known private thread`, async ({ page }, info) => {
      const data = fixtures(info);
      await login(page, data.accounts[account]);
      const enumeration = await page.request.get("/bff/v1/me/classifieds?scope=MANAGE_MESSAGES");
      expect(enumeration.status()).toBe(200); expect(await enumeration.json()).toEqual([]);
      const id = account === "unverified_provider" ? data.conversations.unverified : data.conversations.approval;
      await page.goto(`/panel/leady/${id}`);
      await expect(page.getByText("Nie masz ofert z dostępem do rozmów.", { exact: true })).toBeVisible();
      await expect(page.getByRole("log")).toHaveCount(0);
      await expect(page.getByLabel("Wiadomość", { exact: true })).toHaveCount(0);
      const denied = await page.request.get(`/bff/v1/conversations/${id}`);
      expect(denied.status()).toBe(404);
      await expect(page.locator("main").last()).not.toContainText(data.accounts.seeker.email);
    });
  }

  test("a first-send response lost after commit replays the same UUID and leaves one stored message", async ({ page, baseURL }, info) => {
    const data = fixtures(info);
    // This account owns this scenario only, so no other test can append/report its message.
    const unique = randomUUID();
    const created = await page.request.post("/bff/auth/register", {
      headers: { origin: baseURL!, "x-homies-csrf": "1" },
      data: { email: `fe003-message-${unique}@example.com`, password: `SyntheticOnly-${unique}!`, full_name: "FE003 Message Requester" },
    });
    expect(created.status()).toBe(200);
    const restored = page.waitForResponse(response => response.url().endsWith("/bff/auth/session"));
    await page.goto(`/oferta/${data.listings.instant}`);
    expect((await (await restored).json() as { authenticated: boolean }).authenticated).toBe(true);
    if (info.project.name === "mobile") await page.getByRole("button", { name: "Więcej działań", exact: true }).click();
    await page.getByRole("button", { name: "Napisz", exact: true }).filter({ visible: true }).click();
    const composer = page.getByRole("dialog");
    const body = `Syntetyczna wiadomość ${unique}`;
    await composer.getByLabel("Wiadomość", { exact: true }).fill(body);
    const attempts: { body: string; client_message_id: string }[] = [];
    let committed: Detail | undefined;
    let replayed: Detail | undefined;
    const endpoint = `**/bff/v1/classifieds/${data.listings.instant}/conversations`;
    await page.route(endpoint, async route => {
      if (route.request().method() !== "POST") { await route.continue(); return; }
      attempts.push(route.request().postDataJSON() as { body: string; client_message_id: string });
      // This is a REAL upstream response: the first successful database commit happens
      // before only its browser response is dropped. No API result is fabricated.
      const actual = await route.fetch();
      expect(actual.status()).toBe(201);
      const detail = await actual.json() as Detail;
      if (attempts.length === 1) { committed = detail; await route.abort("failed"); }
      else { replayed = detail; await route.fulfill({ response: actual }); }
    });
    await composer.getByRole("button", { name: "Wyślij", exact: true }).click();
    await expect(composer.getByRole("button", { name: "Ponów tę samą wiadomość", exact: true })).toBeVisible();
    expect(attempts).toHaveLength(1);
    await expect(composer.getByLabel("Wiadomość", { exact: true })).toHaveAttribute("readonly", "");
    await composer.getByRole("button", { name: "Ponów tę samą wiadomość", exact: true }).click();
    await expect(page).toHaveURL(/\/wiadomosci\/[A-Za-z0-9-]+$/);
    expect(attempts).toHaveLength(2);
    expect(attempts[1]).toEqual(attempts[0]);
    expect(attempts[0]!.client_message_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(committed).toBeDefined(); expect(replayed).toBeDefined();
    expect(replayed!.conversation.id).toBe(committed!.conversation.id);
    expect(replayed!.messages[0]!.id).toBe(committed!.messages[0]!.id);
    const stored = await readThread(page, committed!.conversation.id);
    expect(stored.messages).toHaveLength(1);
    expect(stored.messages[0]!.id).toBe(committed!.messages[0]!.id);
    expect(stored.messages[0]!.body).toBe(body);
    await expect(page.getByRole("log").getByText(body, { exact: true })).toHaveCount(1);
    await page.unroute(endpoint);
  });
});
