import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { SaveButton, SavedPage, SavedProvider, SaveSearchButton } from "./saved";
import { e } from "./copy";
import type { Schema } from "./api";
const harness = vi.hoisted(() => ({ session: { user: { id: "account-1", name: "Account One", phoneVerified: false, emailVerified: false }, ready: true, ensure: vi.fn(), refresh: vi.fn(), consume: vi.fn(), resumed: undefined } }));
vi.mock("./session", () => ({ useSession: () => harness.session, RequireSession: ({ children }: { children: ReactNode }) => children }));
// Isolate card presentation only; real API parsing, resource lifecycle and saved state execute.
vi.mock("@/components/listing/listing-card", () => ({ ListingCard: ({ listing }: { listing: { title: string } }) => <article data-testid="listing-card">{listing.title}</article> }));
const fetchMock = vi.fn<typeof fetch>();
const response = (body: unknown, status = 200, headers?: HeadersInit) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
const emptyListings = { items: [], total: 0, limit: 100, offset: 0 };
const search: Schema<"SavedSearchOut"> = { id: "search-1", name: "Moje mieszkania", query: "country_code=PL&max_rent=300000", query_state: "VALID", query_schema_version: 1, version: 7, status: "active", notifications_enabled: false, market_country_code: "PL", baseline_at: "2026-10-20T08:00:00Z", created_at: "2026-10-20T08:00:00Z", updated_at: "2026-10-20T08:00:00Z" };
const savedItem = { saved_id: "save-1", listing_id: "listing-1", saved_at: "2026-10-20T08:00:00Z", availability_status: "NO_LONGER_AVAILABLE", listing: null };
const methodOf = (init?: RequestInit) => init?.method ?? "GET";
const writes = () => fetchMock.mock.calls.filter(([, init]) => methodOf(init) !== "GET");
function mockPage(items: unknown[] = [], searches: unknown[] = []) { fetchMock.mockImplementation(async input => String(input).includes("/saved-searches") ? response({ items: searches, total: searches.length, limit: 50 }) : response({ ...emptyListings, items, total: items.length })); }
function renderSave() { return render(<SavedProvider><SaveButton listingId="listing-1" title="Oferta" /></SavedProvider>); }
function renderPage() { return render(<SavedProvider><SavedPage /></SavedProvider>); }
async function saveButton() { const button = screen.getByRole("button", { name: "Zapisz: Oferta" }); await waitFor(() => expect(button).toBeEnabled()); return button; }
beforeEach(() => {
  vi.clearAllMocks(); fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock);
  harness.session.user = { id: "account-1", name: "Account One", phoneVerified: false, emailVerified: false }; harness.session.ensure.mockResolvedValue(true);
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value() { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value() { this.open = false; } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("saved listing confirmation and reconciliation", () => {
  it("waits for confirmed 204 before changing saved heart, including removal", async () => {
    let complete!: (response: Response) => void;
    fetchMock.mockImplementation(async (_input, init) => methodOf(init) === "GET" ? response(emptyListings) : new Promise(done => { complete = done; }));
    renderSave(); const initial = await saveButton(); fireEvent.click(initial); await waitFor(() => expect(writes()).toHaveLength(1));
    expect(initial).toHaveAttribute("aria-pressed", "false"); expect(initial).toBeDisabled();
    await act(async () => complete(new Response(null, { status: 204 })));
    const saved = await screen.findByRole("button", { name: "Usuń z zapisanych: Oferta" }); expect(saved).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(saved); await waitFor(() => expect(writes()).toHaveLength(2)); expect(saved).toHaveAttribute("aria-pressed", "true");
    await act(async () => complete(new Response(null, { status: 204 })));
    expect(await saveButton()).toHaveAttribute("aria-pressed", "false"); expect(writes().map(([, init]) => init?.method)).toEqual(["POST", "DELETE"]);
  });
  it("keeps refused save unsaved and shows limit recovery without raw error", async () => {
    fetchMock.mockImplementation(async (_input, init) => methodOf(init) === "GET" ? response(emptyListings) : response({ detail: "SAVED_LIMIT: internal limit details" }, 409));
    renderSave(); fireEvent.click(await saveButton()); await screen.findByRole("link", { name: e.saved });
    expect(await saveButton()).toHaveAttribute("aria-pressed", "false"); expect(writes()).toHaveLength(1); expect(screen.queryByText("internal limit details")).not.toBeInTheDocument();
  });
  it("re-reads saved set after unknown 503 without repeating the write", async () => {
    let committed = false;
    fetchMock.mockImplementation(async (_input, init) => { if (methodOf(init) === "GET") return response(committed ? { ...emptyListings, items: [savedItem], total: 1 } : emptyListings); committed = true; return response({ detail: "unknown commit" }, 503); });
    renderSave(); fireEvent.click(await saveButton()); await screen.findByRole("button", { name: "Usuń z zapisanych: Oferta" });
    expect(writes()).toHaveLength(1); expect(fetchMock.mock.calls.filter(([, init]) => methodOf(init) === "GET").length).toBeGreaterThanOrEqual(2);
  });
  it("reconciles after both idempotent transport attempts lose their response", async () => {
    let committed = false;
    fetchMock.mockImplementation(async (_input, init) => { if (methodOf(init) === "GET") return response(committed ? { ...emptyListings, items: [savedItem], total: 1 } : emptyListings); committed = true; throw new TypeError("synthetic lost response"); });
    renderSave(); fireEvent.click(await saveButton()); await waitFor(() => expect(writes()).toHaveLength(2));
    await screen.findByRole("button", { name: "Usuń z zapisanych: Oferta" });
  });
  it("offers recovery after initial saved-set read fails instead of disabling save forever", async () => {
    fetchMock.mockResolvedValueOnce(response({ detail: "temporary failure" }, 503)).mockResolvedValue(response(emptyListings));
    renderSave(); fireEvent.click(await screen.findByRole("button", { name: e.retry })); expect(await saveButton()).toBeEnabled(); expect(writes()).toHaveLength(0);
    fireEvent.click(await saveButton()); await screen.findByRole("button", { name: "Usuń z zapisanych: Oferta" }); expect(writes()).toHaveLength(1);
  });
  it("ignores old account delayed save after account change", async () => {
    let complete!: (response: Response) => void;
    let newAccountRead!: (response: Response) => void;
    let reads = 0;
    fetchMock.mockImplementation(async (_input, init) => {
      if (methodOf(init) !== "GET") return new Promise(done => { complete = done; });
      if (++reads === 1) return response(emptyListings);
      return new Promise(done => { newAccountRead = done; });
    });
    const view = renderSave(); fireEvent.click(await saveButton()); await waitFor(() => expect(writes()).toHaveLength(1));
    harness.session.user = { ...harness.session.user, id: "account-2" }; view.rerender(<SavedProvider><SaveButton listingId="listing-1" title="Oferta" /></SavedProvider>);
    await waitFor(() => expect(reads).toBe(2));
    await act(async () => complete(new Response(null, { status: 204 })));
    await act(async () => newAccountRead(response(emptyListings)));
    expect(await saveButton()).toHaveAttribute("aria-pressed", "false");
  });
  it("loads every saved-id page before deciding a second-page item is unsaved", async () => {
    fetchMock.mockImplementation(async input => response(new URL(String(input), "http://localhost").searchParams.get("offset") === "0" ? { ...emptyListings, total: 101, items: Array.from({ length: 100 }, (_, index) => ({ ...savedItem, listing_id: `other-${index}` })) } : { ...emptyListings, total: 101, offset: 100, items: [savedItem] }));
    renderSave(); expect(await screen.findByRole("button", { name: "Usuń z zapisanych: Oferta" })).toBeEnabled(); expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("offset=100"))).toBe(true);
  });
});

describe("saved page privacy and stored-query validity", () => {
  it("renders only tombstone even when unavailable item has stale title/media/address", async () => {
    mockPage([{ ...savedItem, listing: { id: "listing-1", title: "PRIVATE OLD TITLE", address: "PRIVATE ADDRESS", media: [{ url: "https://private.invalid/photo.jpg" }] } }]);
    renderPage(); await screen.findByRole("heading", { name: e.unavailable });
    expect(screen.queryByTestId("listing-card")).not.toBeInTheDocument(); expect(screen.queryByText(/PRIVATE/)).not.toBeInTheDocument(); expect(screen.queryByRole("img")).not.toBeInTheDocument(); expect(screen.getByRole("button", { name: `${e.unsave}: ${e.unavailable}` })).toBeEnabled();
  });
  it("never requests matches or broad search for initially INVALID query", async () => {
    mockPage([], [{ ...search, query_state: "INVALID", invalid_reason: "INTERNAL_PRIVATE_REASON" }]); renderPage(); await screen.findByText(e.invalidSearch);
    expect(screen.queryByRole("button", { name: e.matches })).not.toBeInTheDocument(); expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/matches") || String(url).includes("/classifieds"))).toBe(false); expect(screen.queryByText("INTERNAL_PRIVATE_REASON")).not.toBeInTheDocument();
  });
  it("removes displayed matches after query becomes INVALID despite an older match response", async () => {
    let invalid = false;
    fetchMock.mockImplementation(async input => { const url = String(input); if (url.includes("/matches")) return response({ items: [{ id: "result-1", title: "PREVIOUS MATCH" }], total: 1 }); if (url.includes("/saved-searches")) return response({ items: [{ ...search, query_state: invalid ? "INVALID" : "VALID" }], total: 1, limit: 50 }); return response(emptyListings); });
    renderPage(); fireEvent.click(await screen.findByRole("button", { name: e.matches })); await screen.findByText("PREVIOUS MATCH"); invalid = true; fireEvent(window, new Event("focus")); await screen.findByText(e.invalidSearch);
    await waitFor(() => expect(screen.queryByText("PREVIOUS MATCH")).not.toBeInTheDocument()); expect(screen.queryByRole("button", { name: e.matches })).not.toBeInTheDocument();
  });
  it("patches expected_version and waits for re-read confirmed state", async () => {
    let updated = false; let complete!: (response: Response) => void;
    fetchMock.mockImplementation(async (input, init) => { if (methodOf(init) === "PATCH") return new Promise(done => { complete = done; }); return String(input).includes("/saved-searches") ? response({ items: [{ ...search, status: updated ? "paused" : "active", version: updated ? 8 : 7 }], total: 1, limit: 50 }) : response(emptyListings); });
    renderPage(); fireEvent.click(await screen.findByRole("button", { name: e.pause })); await waitFor(() => expect(writes()).toHaveLength(1)); expect(JSON.parse(String(writes()[0]?.[1]?.body))).toEqual({ status: "paused", expected_version: 7 });
    expect(screen.getByRole("button", { name: e.pause })).toBeDisabled(); expect(screen.queryByRole("button", { name: e.resume })).not.toBeInTheDocument(); updated = true; await act(async () => complete(response({ ...search, status: "paused", version: 8 }))); await screen.findByRole("button", { name: e.resume });
  });
  it("refreshes stale version conflict and uses replacement version on next explicit patch", async () => {
    let conflict = false;
    fetchMock.mockImplementation(async (input, init) => { if (methodOf(init) === "PATCH") { conflict = true; return response({ detail: "SAVED_SEARCH_CHANGED: stale" }, 409); } return String(input).includes("/saved-searches") ? response({ items: [{ ...search, version: conflict ? 8 : 7 }], total: 1, limit: 50 }) : response(emptyListings); });
    renderPage(); fireEvent.click(await screen.findByRole("button", { name: e.pause })); await screen.findByRole("alert"); await waitFor(() => expect(screen.getByRole("button", { name: e.pause })).toBeEnabled()); await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("saved-searches?limit")).length).toBeGreaterThanOrEqual(2));
    fireEvent.click(screen.getByRole("button", { name: e.pause })); await waitFor(() => expect(writes()).toHaveLength(2)); expect(JSON.parse(String(writes()[1]?.[1]?.body)).expected_version).toBe(8);
  });
  it("accepts saved-search DELETE204 and re-reads list", async () => {
    let deleted = false; fetchMock.mockImplementation(async (input, init) => { if (methodOf(init) === "DELETE") { deleted = true; return new Response(null, { status: 204 }); } return String(input).includes("/saved-searches") ? response({ items: deleted ? [] : [search], total: deleted ? 0 : 1, limit: 50 }) : response(emptyListings); });
    renderPage(); fireEvent.click(await screen.findByRole("button", { name: e.remove })); await screen.findByText(e.emptySearches); expect(screen.queryByText(search.name)).not.toBeInTheDocument();
  });
});

describe("saved-search creation and duplicate location", () => {
  async function open() { render(<SaveSearchButton query="country_code=PL&max_rent=300000" />); fireEvent.click(screen.getByRole("button", { name: e.saveSearch })); const dialog = await screen.findByRole("dialog"); fireEvent.change(within(dialog).getByLabelText(e.searchName), { target: { value: "  Mój wybór  " } }); return dialog; }
  it("sends exact query only on confirmation and defaults alerts off", async () => {
    fetchMock.mockResolvedValue(response(search, 201)); const dialog = await open(); expect(fetchMock).not.toHaveBeenCalled(); expect(within(dialog).getByRole("checkbox")).not.toBeChecked(); fireEvent.click(within(dialog).getByRole("button", { name: e.save })); await within(dialog).findByRole("status"); expect(JSON.parse(String(writes()[0]?.[1]?.body))).toEqual({ name: "Mój wybór", query: "country_code=PL&max_rent=300000", notifications_enabled: false });
  });
  it("links only to safe existing saved-search Location", async () => {
    fetchMock.mockResolvedValue(response({ detail: "SAVED_SEARCH_DUPLICATE: internal details" }, 409, { location: "/v1/me/saved-searches/search-123" })); const dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: e.save })); expect(await screen.findByRole("link", { name: e.openExisting })).toHaveAttribute("href", "/zapisane?wyszukiwanie=search-123#wyszukiwania"); expect(screen.queryByText("internal details")).not.toBeInTheDocument();
  });
  it.each(["https://external.invalid/private", "/v1/me/saved-searches/../admin", "/v1/me/saved-searches/search-123?private=body"])("refuses unsafe duplicate Location %s", async location => {
    fetchMock.mockResolvedValue(response({ detail: "SAVED_SEARCH_DUPLICATE: existing" }, 409, { location })); const dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: e.save })); await screen.findByRole("alert"); expect(screen.queryByRole("link", { name: e.openExisting })).not.toBeInTheDocument();
  });
});
