// FE-UX-KRK-002R UX-R1. The hour comes from the API's zone or is not shown at all:
// each instant below reads differently in UTC, so these fail if any zone is assumed.
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DetailEngagement } from "./detail";
import { ViewingRow } from "./viewings";
import { e } from "./copy";
import { SavedProvider } from "./saved";
import { EngagementProvider } from "./session";
import { viewingTime } from "./viewing-model";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/oferta/listing-1" }));

const WARSAW = "Europe/Warsaw";
const hour = (instant: string, zone?: string | null) => viewingTime(instant, zone)?.match(/\d{1,2}:\d{2}/)?.[0];

describe("viewingTime", () => {
  it.each([
    ["winter, UTC+1", "2026-12-01T12:00:00Z", "13:00", "grudnia"],
    ["summer, UTC+2", "2026-07-01T12:00:00Z", "14:00", "lipca"],
    ["last minute before spring forward", "2026-03-29T00:59:00Z", "01:59", "marca"],
    ["first minute after spring forward", "2026-03-29T01:00:00Z", "03:00", "marca"],
    ["last hour before fall back", "2026-10-25T00:30:00Z", "02:30", "października"],
    ["repeated hour after fall back", "2026-10-25T01:30:00Z", "02:30", "października"],
    ["after fall back", "2026-10-25T02:00:00Z", "03:00", "października"],
    ["local date ahead of the UTC date", "2026-12-31T23:30:00Z", "00:30", "stycznia"],
  ])("Europe/Warsaw: %s", (_name, instant, local, month) => {
    expect(hour(instant, WARSAW)).toBe(local);
    expect(viewingTime(instant, WARSAW)).toContain(month);
    expect(viewingTime(instant, WARSAW)).toContain(WARSAW);
  });

  it("uses the zone it is given, not a Polish default", () => {
    expect(hour("2026-12-01T12:00:00Z", "America/New_York")).toBe("07:00");
  });

});

const account = { authenticated: true, user: { id: "account-a", name: "A", phoneVerified: false, emailVerified: false } };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const listing = { id: "listing-1", title: "Synthetic", contact_mode: "messages", monthly_total_estimate: 100000, utilities_basis: "INCLUDED" as const, currency: "PLN" };
const STARTS = "2099-12-01T12:00:00Z";
const LOCAL = "13:00"; // the same instant in UTC reads 12:00
const fetchMock = vi.fn<typeof fetch>();

function serve(status: string, slots: () => Promise<Response>) {
  fetchMock.mockImplementation(async (path) => {
    if (path === "/bff/auth/session") return response(account);
    if (path === "/bff/v1/me/viewings") return response([{ id: "viewing-1", listing_id: "listing-1", status, starts_at: STARTS }]);
    if (String(path).includes("viewing-slots")) return slots();
    return response([]);
  });
}
const mount = () => render(<EngagementProvider><SavedProvider><DetailEngagement listing={listing} /></SavedProvider></EngagementProvider>);

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe.each([
  ["REQUESTED", "Prośba wysłana — czeka na potwierdzenie"],
  ["CONFIRMED", "Oglądanie potwierdzone"],
])("listing page, %s viewing", (status, label) => {
  it("shows no hour until the zone arrives, then the local one", async () => {
    let release: (value: Response) => void = () => undefined;
    serve(status, () => new Promise((resolve) => { release = resolve; }));
    mount();
    const rail = await screen.findByRole("region", { name: e.railTitle });
    await waitFor(() => expect(rail).toHaveTextContent(label));
    expect(rail).not.toHaveTextContent("UTC");
    expect(rail).not.toHaveTextContent(/\d{1,2}:\d{2}/);
    expect(rail).toHaveTextContent(e.viewingTimeLoading);
    await act(async () => release(response({ slots: [], duration_minutes: 30, timezone: WARSAW })));
    await waitFor(() => expect(rail).toHaveTextContent(LOCAL));
    expect(rail).toHaveTextContent(WARSAW);
    expect(rail).toHaveTextContent(label);
  });

  it("keeps the status and admits it when the zone cannot be read, then recovers on retry", async () => {
    let available = false;
    serve(status, async () => (available ? response({ slots: [], duration_minutes: 30, timezone: WARSAW }) : response({}, 503)));
    mount();
    const rail = await screen.findByRole("region", { name: e.railTitle });
    await waitFor(() => expect(rail).toHaveTextContent(e.viewingTimeUnknown));
    expect(rail).toHaveTextContent(label);
    expect(rail).not.toHaveTextContent("UTC");
    expect(rail).not.toHaveTextContent(/\d{1,2}:\d{2}/);
    available = true;
    await act(async () => within(rail).getByRole("button", { name: e.retry }).click());
    await waitFor(() => expect(rail).toHaveTextContent(LOCAL));
  });

  it("keeps FE-003's explicitly labelled UTC when the API says no schedule exists", async () => {
    serve(status, async () => response({ slots: [], duration_minutes: null, timezone: null }));
    mount();
    const rail = await screen.findByRole("region", { name: e.railTitle });
    await waitFor(() => expect(rail).toHaveTextContent("12:00"));
    expect(rail).toHaveTextContent("(UTC)");
  });

  it("treats a listing with no readable schedule (404) the same way, with no pointless retry", async () => {
    serve(status, async () => response({}, 404));
    mount();
    const rail = await screen.findByRole("region", { name: e.railTitle });
    await waitFor(() => expect(rail).toHaveTextContent("(UTC)"));
    expect(within(rail).queryByRole("button", { name: e.retry })).toBeNull();
  });

  it("keeps the exact instant in the markup once the hour is shown", async () => {
    serve(status, async () => response({ slots: [], duration_minutes: 30, timezone: WARSAW }));
    mount();
    const rail = await screen.findByRole("region", { name: e.railTitle });
    await waitFor(() => expect(rail.querySelector("time")).toHaveAttribute("datetime", STARTS));
  });
});

describe("accessible names of viewing actions follow the same rule as the visible time (F-02)", () => {
  const row = { id: "viewing-1", listing_id: "listing-1", status: "REQUESTED", starts_at: STARTS, ends_at: STARTS, attendee_count: 1, requester_display_name: "Requester", requester_note: null };
  function serveRow(slots: () => Promise<Response>) {
    fetchMock.mockImplementation(async (path) => {
      if (path === "/bff/auth/session") return response(account);
      if (String(path).includes("viewing-slots")) return slots();
      if (String(path).includes("/v1/classifieds/")) return response({ title: "Synthetic" });
      return response([]);
    });
  }
  const mountRow = (provider: boolean) => render(<EngagementProvider><SavedProvider><ViewingRow viewing={row as never} provider={provider} reload={() => undefined} /></SavedProvider></EngagementProvider>);
  const names = (provider: boolean) => (provider ? [e.confirm, e.decline, e.cancelViewing] : [e.cancelViewing]);
  const actionButton = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}`) });

  describe.each([[true, "provider"], [false, "requester"]])("%s (%s)", (provider) => {
    it("names no hour while the zone loads, then the local hour", async () => {
      let release: (value: Response) => void = () => undefined;
      serveRow(() => new Promise((resolve) => { release = resolve; }));
      mountRow(provider);
      await screen.findByText(e.viewingTimeLoading);
      for (const name of names(provider)) {
        expect(actionButton(name).getAttribute("aria-label")).toBe(`${name}: ${e.viewingTimeLoading}`);
      }
      await act(async () => release(response({ slots: [], duration_minutes: 30, timezone: WARSAW })));
      await waitFor(() => expect(actionButton(e.cancelViewing).getAttribute("aria-label")).toContain(LOCAL));
      expect(actionButton(e.cancelViewing).getAttribute("aria-label")).toContain(WARSAW);
      expect(actionButton(e.cancelViewing).getAttribute("aria-label")).not.toContain("UTC");
    });

    it("names no hour when the zone read fails, and recovers on retry", async () => {
      let available = false;
      serveRow(async () => (available ? response({ slots: [], duration_minutes: 30, timezone: WARSAW }) : response({}, 503)));
      mountRow(provider);
      await screen.findByText(new RegExp(e.viewingTimeUnknown));
      for (const name of names(provider)) {
        const label = actionButton(name).getAttribute("aria-label")!;
        expect(label).toBe(`${name}: ${e.viewingTimeUnknown}`);
        expect(label).not.toMatch(/\d{1,2}:\d{2}|UTC/);
      }
      available = true;
      await act(async () => screen.getByRole("button", { name: e.retry }).click());
      await waitFor(() => expect(actionButton(e.cancelViewing).getAttribute("aria-label")).toContain(LOCAL));
    });

    it.each([
      ["timezone: null", () => response({ slots: [], duration_minutes: null, timezone: null })],
      ["404", () => response({}, 404)],
    ])("keeps the labelled UTC fallback when no schedule exists (%s)", async (_name, answer) => {
      serveRow(async () => answer());
      mountRow(provider);
      await waitFor(() => expect(actionButton(e.cancelViewing).getAttribute("aria-label")).toContain("12:00 (UTC)"));
    });
  });
});

it("a past REQUESTED viewing is not offered as the current one on the listing page", async () => {
  fetchMock.mockImplementation(async (path) => {
    if (path === "/bff/auth/session") return response(account);
    if (path === "/bff/v1/me/viewings") return response([{ id: "viewing-1", listing_id: "listing-1", status: "REQUESTED", starts_at: "2020-01-01T12:00:00Z" }]);
    return response([]);
  });
  mount();
  const rail = await screen.findByRole("region", { name: e.railTitle });
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/bff/v1/me/viewings", expect.anything()));
  expect(rail).not.toHaveTextContent("Prośba wysłana");
  expect(screen.queryByRole("link", { name: e.seeViewing })).toBeNull();
  expect(fetchMock.mock.calls.some(([path]) => String(path).includes("viewing-slots"))).toBe(false);
});
