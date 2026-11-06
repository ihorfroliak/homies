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

describe("MapCard freshness", () => {
  it("reads again on every open, so a changed price is shown", async () => {
    const { unmount } = render(<MapCard ids={["fresh-1"]} nearby={false} onClose={() => undefined} />);
    await screen.findByText(/3\s000/);
    unmount();
    vi.mocked(fetch).mockImplementationOnce(async () => new Response(JSON.stringify({ ...listing("fresh-1"), monthly_total_estimate: 123400 }), { status: 200 }));
    render(<MapCard ids={["fresh-1"]} nearby={false} onClose={() => undefined} />);
    await screen.findByText(/1\s234/);
    expect(screen.queryByText(/3\s000/)).toBeNull();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);
  });

  it("does not read a listing again while one card pages through its stack", async () => {
    const ids = idsFor("once", CARD_STEP + 1);
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta once-0" });
    await userEvent.click(screen.getByRole("button", { name: /Pokaż kolejne/ }));
    await screen.findByRole("link", { name: `Oferta once-${CARD_STEP}` });
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(ids.length);
  });

  it("says a removed listing is gone without offering a pointless retry", async () => {
    vi.mocked(fetch).mockImplementation(async () => new Response("{}", { status: 404 }));
    render(<MapCard ids={["gone-1"]} nearby={false} onClose={() => undefined} />);
    expect(await screen.findByText(/nie jest już dostępna/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Spróbuj ponownie" })).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows no remembered price when reading again fails", async () => {
    const { unmount } = render(<MapCard ids={["stale-1"]} nearby={false} onClose={() => undefined} />);
    await screen.findByText(/3\s000/);
    unmount();
    vi.mocked(fetch).mockImplementation(async () => new Response("{}", { status: 503 }));
    render(<MapCard ids={["stale-1"]} nearby={false} onClose={() => undefined} />);
    expect(await screen.findByText(/Nie udało się wczytać/)).toBeInTheDocument();
    expect(screen.queryByText(/3\s000/)).toBeNull();
  });

  it("ignores a slow answer from a card that was closed", async () => {
    let resolveFirst: (value: Response) => void = () => undefined;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }));
    const { unmount } = render(<MapCard ids={["late-1"]} nearby={false} onClose={() => undefined} />);
    unmount();
    vi.mocked(fetch).mockImplementationOnce(async () => new Response(JSON.stringify({ ...listing("late-1"), monthly_total_estimate: 123400 }), { status: 200 }));
    render(<MapCard ids={["late-1"]} nearby={false} onClose={() => undefined} />);
    await screen.findByText(/1\s234/);
    resolveFirst(new Response(JSON.stringify(listing("late-1")), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.getByText(/1\s234/)).toBeInTheDocument();
    expect(screen.queryByText(/3\s000/)).toBeNull();
  });
});

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
