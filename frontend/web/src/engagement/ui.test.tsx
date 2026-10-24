import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ApiError } from "@/api/errors";
import { useCountdown } from "./ui";
function Probe({ error }: { error?: unknown }) { const wait = useCountdown(error); return <button disabled={wait > 0}>{wait}</button>; }
afterEach(() => vi.useRealTimers());
it("blocks immediately on a new Retry-After, counts down, and resets for another refusal", () => {
  vi.useFakeTimers(); const view = render(<Probe />);
  view.rerender(<Probe error={new ApiError({ kind: "rate_limited", status: 429, retryAfterSeconds: 2 })} />);
  expect(screen.getByRole("button")).toBeDisabled(); expect(screen.getByRole("button")).toHaveTextContent("2");
  act(() => vi.advanceTimersByTime(2000)); expect(screen.getByRole("button")).toBeEnabled();
  view.rerender(<Probe error={new ApiError({ kind: "rate_limited", status: 429, retryAfterSeconds: 5 })} />);
  expect(screen.getByRole("button")).toBeDisabled(); expect(screen.getByRole("button")).toHaveTextContent("5");
});
