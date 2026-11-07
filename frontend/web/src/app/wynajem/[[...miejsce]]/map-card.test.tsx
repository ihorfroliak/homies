import { act, render, screen, waitFor } from "@testing-library/react";
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

describe("MapCard focus after paging and retry (F-01)", () => {
  const answer = (rule: (id: string) => number) =>
    vi.mocked(fetch).mockImplementation(async (url) => {
      const id = decodeURIComponent(String(url).split("/").pop()!);
      const status = rule(id);
      return status === 200 ? new Response(JSON.stringify(listing(id)), { status }) : new Response("{}", { status });
    });
  const lastPage = () => (id: string) => Number(id.split("-").pop()) >= CARD_STEP;
  const next = () => userEvent.click(screen.getByRole("button", { name: /Pokaż kolejne/ }));

  it("moves to Retry when the whole last page fails", async () => {
    const ids = idsFor("all503", CARD_STEP + 2);
    answer((id) => (lastPage()(id) ? 503 : 200));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta all503-0" });
    await next();
    const retry = await screen.findByRole("button", { name: "Spróbuj ponownie" });
    await waitFor(() => expect(document.activeElement).toBe(retry));
  });

  it("moves to the close button when the whole last page is gone", async () => {
    const ids = idsFor("all404", CARD_STEP + 2);
    answer((id) => (lastPage()(id) ? 404 : 200));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta all404-0" });
    await next();
    await screen.findByText(/Już niedostępne/);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Zamknij" })));
  });

  it("prefers a real new listing when the last page is mixed", async () => {
    const ids = idsFor("mixed", CARD_STEP + 3);
    answer((id) => (id === `mixed-${CARD_STEP}` ? 404 : id === `mixed-${CARD_STEP + 1}` ? 503 : 200));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta mixed-0" });
    await next();
    const added = await screen.findByRole("link", { name: `Oferta mixed-${CARD_STEP + 2}` });
    await waitFor(() => expect(document.activeElement).toBe(added));
  });

  it("moves to Retry when a page is mixed but only unreadable and gone", async () => {
    const ids = idsFor("nolink", CARD_STEP + 2);
    answer((id) => (id === `nolink-${CARD_STEP}` ? 404 : id === `nolink-${CARD_STEP + 1}` ? 503 : 200));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta nolink-0" });
    await next();
    const retry = await screen.findByRole("button", { name: "Spróbuj ponownie" });
    await waitFor(() => expect(document.activeElement).toBe(retry));
  });

  it("a successful retry lands on the listing it recovered", async () => {
    const ids = idsFor("retryok", CARD_STEP + 1);
    let down = true;
    answer((id) => (down && id === `retryok-${CARD_STEP}` ? 503 : 200));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta retryok-0" });
    await next();
    const retry = await screen.findByRole("button", { name: "Spróbuj ponownie" });
    down = false;
    await userEvent.click(retry);
    const recovered = await screen.findByRole("link", { name: `Oferta retryok-${CARD_STEP}` });
    await waitFor(() => expect(document.activeElement).toBe(recovered));
  });

  it("a failed retry keeps focus on Retry, also while it waits", async () => {
    const ids = idsFor("retrybad", CARD_STEP + 1);
    answer((id) => (id === `retrybad-${CARD_STEP}` ? 503 : 200));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta retrybad-0" });
    await next();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Spróbuj ponownie" })));
    let release: (value: Response) => void = () => undefined;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    await act(async () => release(new Response("{}", { status: 503 })));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Spróbuj ponownie" })));
  });

  it("keeps focus on the paging control while the last page loads", async () => {
    const ids = idsFor("waiting", CARD_STEP + 1);
    let release: (value: Response) => void = () => undefined;
    answer(() => 200);
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await screen.findByRole("link", { name: "Oferta waiting-0" });
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    await next();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /Pokaż kolejne/ }));
    await act(async () => release(new Response(JSON.stringify(listing(`waiting-${CARD_STEP}`)), { status: 200 })));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("link", { name: `Oferta waiting-${CARD_STEP}` })));
  });
});

describe("MapCard superseded reads (F-03)", () => {
  it("an old read finishing after the next page loaded does not take that page away", async () => {
    const ids = idsFor("race", CARD_STEP + 1);
    const held: ((value: Response) => void)[] = [];
    // The first page hangs and, like any late response, ignores the abort.
    vi.mocked(fetch).mockImplementation((url) => new Promise((resolve) => {
      held.push(() => resolve(new Response(JSON.stringify(listing(decodeURIComponent(String(url).split("/").pop()!))), { status: 200 })));
    }));
    render(<MapCard ids={ids} nearby={false} onClose={() => undefined} />);
    await waitFor(() => expect(held).toHaveLength(CARD_STEP));
    const oldReads = held.splice(0);
    vi.mocked(fetch).mockImplementation(async (url) => new Response(JSON.stringify(listing(decodeURIComponent(String(url).split("/").pop()!))), { status: 200 }));
    await userEvent.click(screen.getByRole("button", { name: /Pokaż kolejne/ }));
    await screen.findByRole("link", { name: `Oferta race-${CARD_STEP}` });
    await act(async () => {
      for (const finish of oldReads) finish(new Response());
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(screen.getAllByRole("link")).toHaveLength(ids.length);
    expect(screen.queryByRole("status")).toBeNull();
  });
});

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
