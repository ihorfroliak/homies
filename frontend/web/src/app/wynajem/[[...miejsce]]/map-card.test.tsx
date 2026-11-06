import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CARD_STEP, MapCard } from "./map-card";

const listing = (id: string) => ({ id, title: `Oferta ${id}`, city: "Kraków", district: "Kazimierz", media: [], monthly_total_estimate: 300000, utilities_basis: "INCLUDED", currency: "PLN" });
let refused: Set<string>;

beforeEach(() => {
  refused = new Set();
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const id = decodeURIComponent(url.split("/").pop()!);
    return refused.has(id) ? new Response("{}", { status: 429 }) : new Response(JSON.stringify(listing(id)), { status: 200 });
  }));
});
afterEach(() => vi.unstubAllGlobals());

// The module caches details across tests; unique ids keep each case honest.
const idsFor = (prefix: string, n: number) => Array.from({ length: n }, (_, i) => `${prefix}-${i}`);

describe("MapCard", () => {
  it("reaches every listing of a large stack through explicit paging", async () => {
    const ids = idsFor("large", CARD_STEP + 3);
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    expect(await screen.findByRole("link", { name: "Oferta large-0" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: `Oferta large-${CARD_STEP}` })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Pokaż kolejne/ }));
    expect(await screen.findByRole("link", { name: `Oferta large-${CARD_STEP + 2}` })).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(ids.length);
    expect(screen.queryByRole("button", { name: /Pokaż kolejne/ })).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("link", { name: `Oferta large-${CARD_STEP}` })));
  });

  it("says when a listing could not be read and retries on request", async () => {
    refused.add("fail-1");
    render(<MapCard ids={idsFor("fail", 2)} nearby={false} onClose={() => undefined} />);
    expect(await screen.findByText(/Nie udało się wczytać: 1 oferta/)).toBeInTheDocument();
    refused.clear();
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByRole("link", { name: "Oferta fail-1" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Nie udało się wczytać/)).toBeNull());
  });

  it("takes focus on open, closes on Escape and names nearby groups honestly", async () => {
    const onClose = vi.fn();
    render(<MapCard ids={idsFor("focus", 2)} nearby onClose={onClose} onZoom={() => undefined} />);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Zamknij" }));
    expect(screen.getByRole("dialog", { name: "2 oferty w pobliżu" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Przybliż mapę tutaj" })).toBeInTheDocument();
    await screen.findByRole("link", { name: "Oferta focus-0" });
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
