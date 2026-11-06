import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import RouteError from "./error";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

it("retry asks the server again before re-rendering, and never shows the error message", async () => {
  const reset = vi.fn();
  render(<RouteError error={Object.assign(new Error("internal detail"), { digest: "123" })} reset={reset} />);
  expect(screen.queryByText(/internal detail/)).toBeNull();
  expect(screen.getByText("123")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
  await waitFor(() => expect(reset).toHaveBeenCalledTimes(1));
  expect(refresh).toHaveBeenCalledTimes(1);
});
