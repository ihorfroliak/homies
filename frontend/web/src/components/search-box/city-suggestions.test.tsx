import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { CitySuggestions } from "./city-suggestions";
import { SearchBox } from "./search-box";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("starts Kraków Home with an explicit, editable city", () => {
  render(<SearchBox />);
  expect(screen.getByLabelText("Miasto")).toHaveValue("Kraków");
  fireEvent.change(screen.getByLabelText("Miasto"), { target: { value: "Warszawa" } });
  expect(screen.getByLabelText("Miasto")).toHaveValue("Warszawa");
});

it("aborts immediately when cleared and rejects a late response even when transport ignores abort", async () => {
  vi.useFakeTimers();
  let resolve!: (value: Response) => void;
  const fetchMock = vi.fn(() => new Promise<Response>((done) => { resolve = done; }));
  vi.stubGlobal("fetch", fetchMock);
  render(<><input id="city" aria-label="Miasto" /><CitySuggestions inputId="city" listId="cities" /></>);
  fireEvent.input(screen.getByRole("textbox"), { target: { value: "Krak" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(250); });
  const signal = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].signal!;
  fireEvent.input(screen.getByRole("textbox"), { target: { value: "" } });
  expect(signal.aborted).toBe(true);
  await act(async () => { resolve(new Response(JSON.stringify([{ name: "Kraków", kind: "CITY" }]))); });
  expect(document.querySelectorAll("option")).toHaveLength(0);
});

it("ignores an old query while the replacement is still being debounced", async () => {
  vi.useFakeTimers();
  const requests: ((value: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => requests.push(resolve))));
  render(<><input id="city" aria-label="Miasto" /><CitySuggestions inputId="city" listId="cities" /></>);
  fireEvent.input(screen.getByRole("textbox"), { target: { value: "Krak" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(250); });
  fireEvent.input(screen.getByRole("textbox"), { target: { value: "Wars" } });
  await act(async () => { requests[0]!(new Response(JSON.stringify([{ name: "Kraków", kind: "CITY" }]))); });
  expect(document.querySelectorAll("option")).toHaveLength(0);
  await act(async () => { await vi.advanceTimersByTimeAsync(250); });
  await act(async () => { requests[1]!(new Response(JSON.stringify([{ name: "Warszawa", kind: "CITY" }]))); });
  expect(document.querySelector("option")).toHaveValue("Warszawa");
});
