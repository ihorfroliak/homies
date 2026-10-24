import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/errors";
const state = vi.hoisted(() => ({ api: vi.fn(), block: vi.fn(), user: { id: "user", phoneVerified: true }, blocked: new Set<string>() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/oferta/listing" }));
vi.mock("./session", () => ({ useSession: () => ({ user: state.user, blocked: state.blocked, ensure: async () => true, block: state.block, refresh: async () => undefined }) }));
vi.mock("./api", async () => ({ ...await vi.importActual<typeof import("./api")>("./api"), api: state.api }));
vi.mock("./ui", async () => { const actual = await vi.importActual<typeof import("./ui")>("./ui"); return { ...actual, useResource: () => ({ data: { remaining: 20, limit: 20 }, reload: vi.fn() }) }; });
import { ContactReveal } from "./contact";
beforeEach(() => { vi.clearAllMocks(); state.blocked.clear(); });
describe("phone disclosure minimisation", () => {
  it("clears the previous phone before a refusal and restricts the other engagement surfaces", async () => {
    state.api.mockResolvedValueOnce({ contact_phone: "+48123456789" }).mockRejectedValueOnce(new ApiError({ kind: "conflict", status: 409, code: "RECONTACT_BLOCKED" }));
    render(<ContactReveal listingId="listing" onMessage={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Pokaż numer" })); await screen.findByRole("link", { name: "+48123456789" });
    fireEvent.click(screen.getByRole("button", { name: "Pokaż numer" })); expect(screen.queryByText("+48123456789")).toBeNull();
    await waitFor(() => expect(state.block).toHaveBeenCalledWith("listing")); expect(document.querySelector('a[href^="tel:"]')).toBeNull();
  });
  it("clears disclosed number on loss of browser focus", async () => { state.api.mockResolvedValueOnce({ contact_phone: "+48123456789" }); render(<ContactReveal listingId="listing" onMessage={() => undefined} />); fireEvent.click(screen.getByRole("button", { name: "Pokaż numer" })); await screen.findByText("+48123456789"); fireEvent(window, new Event("blur")); expect(screen.queryByText("+48123456789")).toBeNull(); });
  it("does not redisclose a delayed response after focus was lost", async () => {
    let complete!: (value: { contact_phone: string }) => void;
    state.api.mockReturnValueOnce(new Promise(resolve => { complete = resolve; }));
    render(<ContactReveal listingId="listing" onMessage={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Pokaż numer" }));
    await waitFor(() => expect(state.api).toHaveBeenCalled());
    fireEvent(window, new Event("blur")); complete({ contact_phone: "+48123456789" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Pokaż numer" })).toHaveAttribute("aria-busy", "false"));
    expect(document.querySelector('a[href^="tel:"]')).toBeNull();
  });
});
