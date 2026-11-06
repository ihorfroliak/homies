import { openNavigation } from "./navigation-helper";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

type Account = { email: string; password: string };
type Fixtures = {
  accounts: Record<"seeker" | "provider" | "unverified_provider" | "host_without_authority", Account>;
  listings: Record<"instant" | "held" | "past_requested" | "past_confirmed" | "unverified", string>;
  viewings: Record<"held" | "past_requested" | "past_confirmed" | "unverified", string>;
};
type Viewing = { id: string; listing_id: string; starts_at: string; status: string };
function fixtures(info: TestInfo): Fixtures {
  const file = process.env.E2E_ENGAGEMENT_MANIFEST;
  if (!file || !isAbsolute(file)) throw new Error("Private absolute E2E_ENGAGEMENT_MANIFEST required");
  const value = JSON.parse(readFileSync(file, "utf8")) as { version: number; projects: Record<string, Fixtures> };
  const result = value.projects[info.project.name];
  if (value.version !== 1 || !result?.accounts?.seeker || !result.viewings?.past_confirmed || !result.listings?.instant) throw new Error("Incomplete engagement fixture manifest");
  return result;
}
async function login(page: Page, account: Account) {
  await page.goto("/logowanie");
  await page.getByLabel("E-mail", { exact: true }).fill(account.email);
  await page.getByLabel("Hasło", { exact: true }).fill(account.password);
  await page.locator("form").getByRole("button", { name: "Zaloguj się", exact: true }).last().click();
  await expect(page.getByRole("status").filter({ hasText: "Zalogowano" })).toBeVisible();
}
async function providerSection(page: Page, listingId: string) {
  const enumeration = await page.request.get("/bff/v1/me/classifieds?scope=MANAGE_VIEWINGS");
  expect(enumeration.status()).toBe(200);
  const listing = (await enumeration.json() as { id: string; title: string }[]).find(row => row.id === listingId);
  expect(listing).toBeDefined();
  return page.locator("section").filter({ has: page.getByRole("heading", { level: 2, name: listing!.title, exact: true }) });
}
async function readViewings(page: Page, path = "/bff/v1/me/viewings"): Promise<Viewing[]> {
  const response = await page.request.get(path); expect(response.status()).toBe(200);
  return response.json() as Promise<Viewing[]>;
}

// This suite alone mutates past_confirmed. Other seeded rows are read-only (held
// confirmation must be refused). Instant scenarios each register a fresh requester
// and select different slots; desktop/mobile use separate fixture inventories.
// No private credentials, notes or responses are retained in browser artifacts.
test.use({ trace: "off", screenshot: "off", video: "off" });
test.describe("FE-003 viewing lifecycle with real API", () => {
  test.skip(process.env.E2E_ENGAGEMENT !== "1", "Requires disposable engagement fixtures");

  for (const [listingKey, status, label, slotIndex] of [["approval", "REQUESTED", "Prośba wysłana — czeka na potwierdzenie", 2], ["instant", "CONFIRMED", "Oglądanie potwierdzone", 2]] as const) {
    test(`listing page shows no guessed hour for a ${status} viewing while its zone is unknown`, async ({ page, baseURL }, info) => {
      const listing = (fixtures(info).listings as unknown as Record<string, string>)[listingKey]!;
      const unique = randomUUID();
      const headers = { origin: baseURL!, "x-homies-csrf": "1" };
      expect((await page.request.post("/bff/auth/register", { headers, data: { email: `zone-${unique}@example.com`, password: `Fictional-${unique}!`, full_name: "Tester Strefy" } })).status()).toBe(200);
      const open = await (await page.request.get(`/bff/v1/classifieds/${listing}/viewing-slots?days=14`)).json() as { slots: string[]; timezone: string };
      expect(open.slots.length).toBeGreaterThan(slotIndex);
      const startsAt = open.slots[slotIndex]!;
      const created = await page.request.post(`/bff/v1/classifieds/${listing}/viewings`, { headers, data: { starts_at: startsAt, attendee_count: 1, note: null } });
      expect(created.status()).toBe(201);
      const local = new Intl.DateTimeFormat("pl-PL", { timeZone: open.timezone, hour: "2-digit", minute: "2-digit" }).format(new Date(startsAt));
      const status_ = page.getByText(label, { exact: true }).filter({ visible: true }).locator("xpath=..");

      // Delayed zone: the status is there, an hour is not.
      let release: () => void = () => undefined;
      const held = new Promise<void>((resolve) => { release = resolve; });
      await page.route(/\/viewing-slots\?days=1$/, async (route) => { await held; await route.continue().catch(() => undefined); });
      await page.goto(`/oferta/${listing}`);
      await expect(status_).toBeVisible();
      await expect(status_).not.toContainText("UTC");
      await expect(status_).not.toContainText(/\d{1,2}:\d{2}/);
      release();
      await expect(status_).toContainText(local);
      await expect(status_).toContainText(open.timezone);
      await page.unroute(/\/viewing-slots\?days=1$/);

      // Failed zone: still no guess; retry recovers from the real API.
      await page.route(/\/viewing-slots\?days=1$/, (route) => route.fulfill({ status: 503, contentType: "application/json", body: "{}" }));
      await page.goto(`/oferta/${listing}`);
      await expect(status_).toBeVisible();
      await expect(status_).toContainText("Nie udało się ustalić godziny");
      await expect(status_).not.toContainText("UTC");
      await expect(status_).not.toContainText(/\d{1,2}:\d{2}/);
      await page.unroute(/\/viewing-slots\?days=1$/);
      await status_.getByRole("button", { name: "Spróbuj ponownie" }).click();
      await expect(status_).toContainText(local);
    });
  }

  for (const [listingKey, status, label] of [["approval", "REQUESTED", "Prośba wysłana — czeka na potwierdzenie"], ["instant", "CONFIRMED", "Oglądanie potwierdzone"]] as const) {
    test(`listing page labels a ${status} viewing from the server state`, async ({ page, baseURL }, info) => {
      const listing = (fixtures(info).listings as unknown as Record<string, string>)[listingKey]!;
      const unique = randomUUID();
      const headers = { origin: baseURL!, "x-homies-csrf": "1" };
      expect((await page.request.post("/bff/auth/register", { headers, data: { email: `status-${unique}@example.com`, password: `Fictional-${unique}!`, full_name: "Tester Statusu" } })).status()).toBe(200);
      const open = await (await page.request.get(`/bff/v1/classifieds/${listing}/viewing-slots?days=14`)).json() as { slots: string[]; timezone: string };
      expect(open.slots.length).toBeGreaterThan(2);
      // A slot the other parallel scenarios do not take: they use the first and last.
      const created = await page.request.post(`/bff/v1/classifieds/${listing}/viewings`, { headers, data: { starts_at: open.slots[1], attendee_count: 1, note: null } });
      expect(created.status()).toBe(201);
      expect((await created.json() as { status: string }).status).toBe(status);
      await page.goto(`/oferta/${listing}`);
      const shown = page.getByText(label, { exact: true }).filter({ visible: true });
      await expect(shown).toHaveCount(1);
      await expect(page.getByText(open.timezone).filter({ visible: true })).toHaveCount(1);
      await expect(page.getByText(/umówion/i).filter({ visible: true })).toHaveCount(0);
      await expect(page.getByRole("link", { name: "Zobacz moje oglądanie", exact: true }).filter({ visible: true })).toHaveAttribute("href", "/ogladania");
      await expect(page.getByRole("button", { name: "Umów oglądanie", exact: true }).filter({ visible: true })).toHaveCount(0);
    });
  }

  for (const lostResponse of [false, true]) {
    test(`instant booking ${lostResponse ? "reconciles a response lost after commit without a second POST" : "shows the committed CONFIRMED state"}`, async ({ page, baseURL }, info) => {
      const data = fixtures(info); const unique = randomUUID();
      const registered = await page.request.post("/bff/auth/register", {
        headers: { origin: baseURL!, "x-homies-csrf": "1" },
        data: { email: `viewing-${unique}@example.com`, password: `Fictional-${unique}!`, full_name: "Próba Oglądania" },
      });
      expect(registered.status()).toBe(200);
      const session = page.waitForResponse(response => response.url().endsWith("/bff/auth/session"));
      await page.goto(`/oferta/${data.listings.instant}`);
      expect((await (await session).json() as { authenticated: boolean }).authenticated).toBe(true);
      await page.getByRole("button", { name: "Umów oglądanie", exact: true }).filter({ visible: true }).click();
      const picker = page.getByRole("dialog");
      const radios = picker.getByRole("radio").filter({ visible: true });
      await expect(radios.first()).toBeVisible();
      // Distinct visible slots keep the parallel scenarios from competing for capacity.
      expect(await radios.count()).toBeGreaterThan(1);
      const selected = lostResponse ? radios.last() : radios.first();
      await selected.check(); const instant = await selected.inputValue();
      await picker.getByRole("button", { name: "Dalej", exact: true }).click();
      const form = page.getByRole("dialog", { name: "Wyślij prośbę o oglądanie", exact: true });
      await expect(form).toBeVisible();
      const endpoint = `**/bff/v1/classifieds/${data.listings.instant}/viewings`;
      let posts = 0; let committed: Viewing | undefined;
      await page.route(endpoint, async route => {
        if (route.request().method() !== "POST") { await route.continue(); return; }
        posts += 1;
        const actual = await route.fetch(); // REAL commit first; never fabricate a success.
        expect(actual.status()).toBe(201); committed = await actual.json() as Viewing;
        if (lostResponse) await route.abort("failed");
        else await route.fulfill({ response: actual });
      });
      await form.getByRole("button", { name: "Wyślij prośbę o oglądanie", exact: true }).click();
      const result = page.getByRole("dialog", { name: "Moje oglądania", exact: true });
      await expect(result.getByRole("status")).toContainText("Oglądanie potwierdzone");
      expect(posts).toBe(1); expect(committed).toBeDefined(); expect(committed!.status).toBe("CONFIRMED");
      expect(Date.parse(committed!.starts_at)).toBe(Date.parse(instant));
      await result.getByRole("link", { name: "Moje oglądania", exact: true }).click();
      await expect(page).toHaveURL(/\/ogladania$/);
      await expect(page.locator("article").getByRole("status")).toContainText("Oglądanie potwierdzone");
      const rows = (await readViewings(page)).filter(row => row.listing_id === data.listings.instant);
      expect(rows).toHaveLength(1); expect(rows[0]!.id).toBe(committed!.id); expect(rows[0]!.status).toBe("CONFIRMED");
      // Visiting the durable result also must not trigger a blind retry.
      expect(posts).toBe(1);
      await page.unroute(endpoint);
    });
  }

  test("passed REQUESTED stays unchanged and read-only for requester and provider", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.seeker);
    const before = (await readViewings(page)).find(row => row.id === data.viewings.past_requested);
    expect(before?.status).toBe("REQUESTED"); expect(Date.parse(before!.starts_at)).toBeLessThan(Date.now());
    await page.goto("/ogladania");
    const row = page.locator("article").filter({ has: page.getByRole("status").filter({ hasText: "Bez odpowiedzi — termin minął" }) });
    await expect(row).toHaveCount(1); await expect(row.getByRole("button")).toHaveCount(0);
    await openNavigation(page);
    await page.getByRole("button", { name: "Wyloguj się", exact: true }).click();
    await expect(page.getByRole("button", { name: "Wyloguj się", exact: true })).toHaveCount(0);
    await login(page, data.accounts.provider); await page.goto("/panel/ogladania");
    const section = await providerSection(page, data.listings.past_requested);
    await expect(section.getByRole("status")).toContainText("Bez odpowiedzi — termin minął");
    await expect(section.getByRole("button")).toHaveCount(0);
    const after = (await readViewings(page, `/bff/v1/classifieds/${data.listings.past_requested}/viewings`)).find(item => item.id === before!.id);
    expect(after?.status).toBe("REQUESTED"); expect(after?.starts_at).toBe(before!.starts_at);
  });

  test("provider records COMPLETED only for the seeded past confirmed viewing", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.provider);
    const endpoint = `/bff/v1/classifieds/${data.listings.past_confirmed}/viewings`;
    const before = (await readViewings(page, endpoint)).find(row => row.id === data.viewings.past_confirmed);
    expect(before?.status).toBe("CONFIRMED"); expect(Date.parse(before!.starts_at)).toBeLessThan(Date.now());
    await page.goto("/panel/ogladania"); const section = await providerSection(page, data.listings.past_confirmed);
    await expect(section.getByRole("button", { name: /^Odwołaj oglądanie:/ })).toHaveCount(0);
    await expect(section.getByRole("button", { name: /^Nie przyszedł:/ })).toBeVisible();
    const response = page.waitForResponse(item => item.url().endsWith(`/viewings/${before!.id}/outcome`) && item.request().method() === "POST");
    await section.getByRole("button", { name: /^Odbyło się:/ }).click();
    expect((await response).status()).toBe(200);
    await expect(section.getByRole("status")).toContainText("Odbyło się");
    await expect(section.getByRole("button")).toHaveCount(0);
    expect((await readViewings(page, endpoint)).find(row => row.id === before!.id)?.status).toBe("COMPLETED");
    await expect(section).not.toContainText(data.accounts.seeker.email);
  });

  test("held listing refuses confirmation and leaves the request REQUESTED", async ({ page }, info) => {
    const data = fixtures(info); await login(page, data.accounts.provider);
    const endpoint = `/bff/v1/classifieds/${data.listings.held}/viewings`;
    expect((await readViewings(page, endpoint)).find(row => row.id === data.viewings.held)?.status).toBe("REQUESTED");
    await page.goto("/panel/ogladania"); const section = await providerSection(page, data.listings.held);
    const response = page.waitForResponse(item => item.url().endsWith(`/viewings/${data.viewings.held}/confirm`) && item.request().method() === "POST");
    await section.getByRole("button", { name: /^Potwierdź:/ }).click();
    const refused = await response; expect(refused.status()).toBe(409);
    expect((await refused.json() as { detail: string }).detail).toMatch(/^LISTING_HELD:/);
    await expect(section).toContainText("Oferta jest sprawdzana przez Homies — potwierdzanie wstrzymane");
    expect((await readViewings(page, endpoint)).find(row => row.id === data.viewings.held)?.status).toBe("REQUESTED");
  });

  for (const actor of ["unverified_provider", "host_without_authority"] as const) {
    test(`${actor} receives no private viewing rows from Panel or a known listing`, async ({ page }, info) => {
      const data = fixtures(info); await login(page, data.accounts[actor]);
      const enumeration = await page.request.get("/bff/v1/me/classifieds?scope=MANAGE_VIEWINGS");
      expect(enumeration.status()).toBe(200); expect(await enumeration.json()).toEqual([]);
      await page.goto("/panel/ogladania");
      await expect(page.getByRole("heading", { name: "Oglądania w panelu", exact: true })).toBeVisible();
      await expect(page.getByText("Brak próśb o oglądanie", { exact: true })).toBeVisible();
      await expect(page.locator("main article")).toHaveCount(0);
      const listing = actor === "unverified_provider" ? data.listings.unverified : data.listings.past_requested;
      const denied = await page.request.get(`/bff/v1/classifieds/${listing}/viewings`);
      expect(denied.status()).toBe(404);
      const privateId = actor === "unverified_provider" ? data.viewings.unverified : data.viewings.past_requested;
      expect(await denied.text()).not.toContain(privateId);
      await expect(page.locator("main").last()).not.toContainText(data.accounts.seeker.email);
    });
  }
});

