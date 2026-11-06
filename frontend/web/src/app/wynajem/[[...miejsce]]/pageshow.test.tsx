// SYNTHETIC pageshow events: this exercises the handlers' logic only. It does not prove
// that any browser restores these pages from its back/forward cache; e2e/bfcache.spec.ts
// is the place that distinguishes a real restore.
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { AutoSubmit } from "./auto-submit";
import { FilterCount } from "./filter-count";

function pageshow(persisted: boolean) {
  const event = new Event("pageshow") as PageTransitionEvent;
  Object.defineProperty(event, "persisted", { value: persisted });
  act(() => void window.dispatchEvent(event));
}

beforeEach(() => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ total: 5 }), { status: 200 }))));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function SortForm() {
  return (
    <form data-testid="form">
      <select id="s" defaultValue="a" aria-label="sort">
        <option value="a">a</option>
        <option value="b">b</option>
      </select>
      <AutoSubmit selectId="s" />
    </form>
  );
}

function Filters() {
  return (
    <form id="f" data-testid="form">
      <input aria-label="rooms" name="pokoje_od" defaultValue="" />
      <input aria-label="other" name="metraz_od" defaultValue="" />
      <FilterCount formId="f" segments={["krakow"]} initialTotal={10} />
    </form>
  );
}

it("sort: a real restore returns the select to the value of its URL and does not submit", async () => {
  render(<SortForm />);
  const select = screen.getByLabelText<HTMLSelectElement>("sort");
  const submit = vi.spyOn(HTMLFormElement.prototype, "requestSubmit").mockImplementation(() => undefined);
  select.value = "b"; // state a browser would have frozen with the page
  pageshow(true);
  expect(select.value).toBe("a");
  expect(submit).not.toHaveBeenCalled();
  submit.mockRestore();
});

it("sort: an ordinary pageshow changes nothing", () => {
  render(<SortForm />);
  const select = screen.getByLabelText<HTMLSelectElement>("sort");
  select.value = "b";
  pageshow(false);
  expect(select.value).toBe("b");
});

it("filters: restoring a submitted form re-enables its fields and returns them and the count to the URL", async () => {
  render(<Filters />);
  const rooms = screen.getByLabelText<HTMLInputElement>("rooms");
  const other = screen.getByLabelText<HTMLInputElement>("other");
  await userEvent.type(rooms, "4");
  const form = screen.getByTestId<HTMLFormElement>("form");
  form.addEventListener("submit", (event) => event.preventDefault());
  act(() => void form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  expect(other.disabled).toBe(true); // empty fields leave the URL by being disabled on submit
  pageshow(true);
  expect(other.disabled).toBe(false);
  expect(rooms.value).toBe("");
  expect(screen.getByRole("button")).toHaveTextContent("10");
});

it("filters: restoring a form the user never submitted keeps what they typed", async () => {
  render(<Filters />);
  const rooms = screen.getByLabelText<HTMLInputElement>("rooms");
  await userEvent.type(rooms, "4");
  pageshow(true);
  expect(rooms.value).toBe("4");
});

it("filters: an ordinary pageshow changes nothing", async () => {
  render(<Filters />);
  const rooms = screen.getByLabelText<HTMLInputElement>("rooms");
  await userEvent.type(rooms, "4");
  pageshow(false);
  expect(rooms.value).toBe("4");
});
