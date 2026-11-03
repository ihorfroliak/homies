import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { HomeOffersMap } from "./home-offers-map";
import { matchRoute } from "@/server/bff-routes";

vi.mock("@/app/wynajem/[[...miejsce]]/map-section", () => ({
  MapSection: ({ initial }: { initial: { points: { id: string }[] } }) => <div data-testid="public-map">{initial.points.map((p) => p.id).join(",")}</div>,
}));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const response = (value: unknown) => ({ ok: true, json: async () => value });
const city = { id: "krk-public-id", kind: "CITY", slug: "krakow" };

it("resolves the city and sends only its ID to the existing public map endpoint", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response([city])).mockResolvedValueOnce(response({ points: [{ id: "offer-a" }], total: 1 }));
  vi.stubGlobal("fetch", fetcher);
  render(<HomeOffersMap />);
  await waitFor(() => expect(screen.getByTestId("public-map")).toHaveTextContent("offer-a"));
  for (const [url] of fetcher.mock.calls) {
    const path = new URL(url as string, "http://localhost").pathname.replace(/^\/bff/, "");
    expect(matchRoute("GET", path)).toBeDefined();
  }
  expect(fetcher.mock.calls[1]?.[0]).toBe("/bff/v1/classifieds/map?locality_id=krk-public-id");
  expect(screen.getByRole("link", { name: /Otwórz mapę/ })).toHaveAttribute("href", "/wynajem/krakow?widok=mapa");
});

it("never broadens a missing city to national results and supports an explicit retry", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response([]));
  vi.stubGlobal("fetch", fetcher);
  render(<HomeOffersMap />);
  await screen.findByRole("button", { name: "Spróbuj ponownie" });
  expect(fetcher).toHaveBeenCalledTimes(1);
  fetcher.mockResolvedValueOnce(response([city])).mockResolvedValueOnce(response({ points: [], total: 0 }));
  fireEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
  await screen.findByText(/Nie ma teraz ofert/);
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it("aborts outstanding map reads when the user returns to districts", () => {
  const fetcher = vi.fn().mockReturnValue(new Promise(() => {}));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<HomeOffersMap />);
  const signal = fetcher.mock.calls[0]?.[1].signal as AbortSignal;
  view.unmount();
  expect(signal.aborted).toBe(true);
});
