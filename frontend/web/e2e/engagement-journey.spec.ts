import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

type Account = { email: string; password: string };
type Fixture = { accounts: Record<string, Account>; listings: Record<string, string>; viewings: Record<string, string> };
function fixture(info: TestInfo): Fixture {
  const file = process.env.E2E_ENGAGEMENT_MANIFEST;
  if (!file || !isAbsolute(file)) throw new Error("Private absolute engagement manifest required");
  const data = JSON.parse(readFileSync(file, "utf8")) as { version: number; projects: Record<string, Fixture> };
  if (data.version !== 1 || !data.projects[info.project.name]) throw new Error("Unsupported fixture manifest");
  return data.projects[info.project.name]!;
}
const fresh = (): Account => ({ email: `journey-${randomUUID()}@example.com`, password: `Fictional-${randomUUID()}!` });
async function credentials(page: Page, account: Account, register = false) {
  const form = page.locator("dialog[open] form").or(page.locator("main form"));
  if (register) await form.getByRole("button", { name: "Utwórz konto", exact: true }).first().click();
  await form.getByLabel("E-mail", { exact: true }).fill(account.email);
  await form.getByLabel("Hasło", { exact: true }).fill(account.password);
  if (register) await form.getByLabel("Imię i nazwisko", { exact: true }).fill("Próba Syntetyczna");
  await form.getByRole("button", { name: register ? "Utwórz konto" : "Zaloguj się", exact: true }).last().click();
}
async function login(page: Page, account: Account) { await page.goto("/logowanie"); await credentials(page, account); await expect(page.getByRole("status").filter({ hasText: "Zalogowano" })).toBeVisible(); }
async function logout(page: Page) { await page.getByRole("button", { name: "Wyloguj się", exact: true }).click(); await expect(page.getByRole("button", { name: "Wyloguj się", exact: true })).toHaveCount(0); }
async function scan(page: Page) { expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations.map(v => v.id)).toEqual([]); }
async function assertPrivateStorage(page: Page) {
  const stored = await page.evaluate(() => [...Object.values(localStorage), ...Object.values(sessionStorage)].join(" "));
  expect(stored).not.toMatch(/access_token|refresh_token|Fictional-|Próba Syntetyczna|@example\.test|client_message_id/);
}
test.use({ trace: "off", screenshot: "off", video: "off" });
test.skip(process.env.E2E_ENGAGEMENT !== "1", "Requires disposable engagement fixtures");

test("guest save resumes registration; saved search versions, delete204 and logout clear private UI", async ({ page }, info) => {
  const writes: number[] = []; page.on("response", response => { if (response.url().includes("/saved-listings/") && response.request().method() === "POST") writes.push(response.status()); });
  const f = fixture(info); await page.goto(`/oferta/${f.listings.approval}`);
  await page.getByRole("button", { name: /^Zapisz:/ }).filter({ visible: true }).click();
  const dialog = page.getByRole("dialog", { name: "Zaloguj się, aby kontynuować" });
  await expect(dialog.getByLabel("E-mail", { exact: true })).toBeFocused(); await scan(page);
  await credentials(page, fresh(), true); await expect(dialog).toHaveCount(0);
  await expect.poll(() => writes).toEqual([201]);
  await expect(page.getByRole("button", { name: /^Usuń z zapisanych:/ }).filter({ visible: true })).toHaveAttribute("aria-pressed", "true");
  const state = await (await page.request.get("/bff/auth/session")).json();
  expect(Object.keys(state.user).sort()).toEqual(["emailVerified", "id", "name", "phoneVerified"]);
  await assertPrivateStorage(page); await page.goto("/zapisane");
  await expect(page.locator("main article")).toHaveCount(1);
  await page.getByRole("button", { name: /^Usuń z zapisanych:/ }).click();
  await expect(page.getByText("Nie masz jeszcze zapisanych ofert", { exact: true })).toBeVisible();
  await page.goto("/wynajem/lublin?koszt_do=5000");
  await page.getByRole("button", { name: "Zapisz wyszukiwanie", exact: true }).click();
  await page.getByLabel("Nazwa wyszukiwania", { exact: true }).fill("Próba Lublin");
  const saved = page.waitForResponse(r => r.url().endsWith("/bff/v1/me/saved-searches") && r.request().method() === "POST");
  await page.getByRole("dialog").getByRole("button", { name: "Zapisz", exact: true }).click(); expect((await saved).status()).toBe(201);
  await page.goto("/zapisane");
  const row = page.locator("#wyszukiwania li").filter({ hasText: "Próba Lublin" });
  await row.getByRole("button", { name: "Wstrzymaj", exact: true }).click(); await expect(row.getByRole("button", { name: "Wznów", exact: true })).toBeVisible();
  await row.getByRole("button", { name: "Usuń", exact: true }).click(); await expect(row).toHaveCount(0);
  await logout(page); await expect(page.locator("main")).not.toContainText("Próba Lublin");
});

test("guest selects exact slot before auth, revalidates, provider confirms and requester cancels", async ({ page }, info) => {
  const f = fixture(info); const account = fresh(); await page.goto(`/oferta/${f.listings.approval}`);
  await page.getByRole("button", { name: "Umów oglądanie", exact: true }).filter({ visible: true }).click();
  const picker = page.getByRole("dialog"); const radio = picker.getByRole("radio").filter({ visible: true }).first();
  await radio.check(); const instant = await radio.inputValue();
  await picker.getByRole("button", { name: "Dalej", exact: true }).click(); await credentials(page, account, true);
  await expect(page.getByRole("dialog", { name: "Wyślij prośbę o oglądanie" })).toBeVisible(); await scan(page);
  const request = page.waitForResponse(r => r.url().endsWith(`/classifieds/${f.listings.approval}/viewings`) && r.request().method() === "POST");
  await page.getByRole("button", { name: "Wyślij prośbę o oglądanie", exact: true }).click();
  const response = await request; expect(response.status()).toBe(201);
  const viewing = await response.json() as { id: string; starts_at: string; status: string }; expect(Date.parse(viewing.starts_at)).toBe(Date.parse(instant)); expect(viewing.status).toBe("REQUESTED");
  await page.getByRole("dialog").getByRole("button", { name: "Zamknij" }).click(); await logout(page);
  await login(page, f.accounts.provider!); await page.goto("/panel/ogladania");
  const providerRow = page.locator("article").filter({ hasText: "Próba S." });
  await expect(providerRow).toHaveCount(1); await expect(providerRow).not.toContainText(account.email);
  await providerRow.getByRole("button", { name: /^Potwierdź:/ }).click(); await expect(providerRow).toContainText("Oglądanie potwierdzone");
  await logout(page); await login(page, account); await page.goto("/ogladania");
  await page.getByRole("button", { name: /^Odwołaj oglądanie:/ }).click(); await page.getByRole("dialog").getByRole("button", { name: "Odwołaj oglądanie", exact: true }).click();
  await expect(page.locator("article")).toContainText("Oglądanie odwołane"); await assertPrivateStorage(page);
});
