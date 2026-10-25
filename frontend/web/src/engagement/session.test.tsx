import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EngagementProvider, RequireSession, useSession } from "./session";
import { Composer, ConversationWorkspace } from "./conversations";
import { EngagementNavigation } from "./navigation";
import { INTENT_KEY, INTENT_TTL } from "./intent";

const fetchMock = vi.fn<typeof fetch>();
const a = { authenticated: true, user: { id: "account-a", name: "Anna", phoneVerified: false, emailVerified: false } };
const b = { authenticated: true, user: { ...a.user, id: "account-b", name: "Beata" } };
const anonymous = { authenticated: false };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const message = { id: "message-1", body: "Private pending text", message_type: "USER", moderation_state: "NONE", created_at: "2026-10-20T10:00:00Z", sender_user_id: a.user.id, sender_organization_id: null };
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
let frames: FrameRequestCallback[] = [];
function Probe({ onResume = () => undefined, compose = false }: { onResume?: (value: boolean) => void; compose?: boolean }) {
  const session = useSession();
  return <><output aria-label="identity">{session.ready ? session.user?.id ?? "anonymous" : "loading"}</output>
    <output aria-label="resumed">{JSON.stringify(session.resumed ?? null)}</output>
    <output aria-label="blocked">{[...session.blocked].join(",")}</output>
    <button id="open-message" onClick={() => void session.ensure({ action: "message", listing_id: "listing-1", initiator_id: "open-message" }).then(onResume)}>Start message</button>
    <button onClick={() => void session.refresh().catch(() => undefined)}>Refresh identity</button>
    <button onClick={() => session.block("listing-1")}>Remember restriction</button>
    <button onClick={session.consume}>Consume intent</button>
    {compose && <RequireSession><Composer conversationId="thread-1" listingId="listing-1" /></RequireSession>}
  </>;
}
function mount(props: Parameters<typeof Probe>[0] = {}, navigation = false) {
  return render(<EngagementProvider><Probe {...props} />{navigation && <ul><EngagementNavigation /></ul>}</EngagementProvider>);
}
const identity = () => screen.getByLabelText("identity");
const sessionCalls = () => fetchMock.mock.calls.filter(([path]) => path === "/bff/auth/session");
const writes = () => fetchMock.mock.calls.filter(([path, init]) => path === "/bff/v1/conversations/thread-1/messages" && init?.method === "POST");
async function settleFrames() { await act(async () => { for (const callback of frames.splice(0)) callback(performance.now()); }); }
async function makePending() {
  await waitFor(() => expect(identity()).toHaveTextContent(a.user.id));
  fireEvent.change(screen.getByLabelText("Wiadomość"), { target: { value: "Private pending text" } });
  fireEvent.click(screen.getByRole("button", { name: "Wyślij" }));
  await screen.findByRole("button", { name: "Ponów tę samą wiadomość" });
}

beforeEach(() => {
  fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); frames = []; sessionStorage.clear(); localStorage.clear();
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value() { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value() { this.open = false; } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("real EngagementProvider auth intents", () => {
  it("restores only allowlisted intent fields after the authenticated session resolves", async () => {
    const session = deferred<Response>(); fetchMock.mockReturnValue(session.promise);
    sessionStorage.setItem(INTENT_KEY, JSON.stringify({ action: "message", listing_id: "listing-1", initiator_id: "open-message", created_at: Date.now(), body: "private draft", password: "never restore" }));
    mount(); expect(screen.getByLabelText("resumed")).toHaveTextContent("null");
    await act(async () => session.resolve(response(a)));
    await waitFor(() => expect(identity()).toHaveTextContent(a.user.id));
    const resumed = JSON.parse(screen.getByLabelText("resumed").textContent!);
    expect(Object.keys(resumed).sort()).toEqual(["action", "created_at", "initiator_id", "listing_id"]);
    expect(resumed.action).toBe("message"); expect(sessionStorage.getItem(INTENT_KEY)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Consume intent" }));
    expect(screen.getByLabelText("resumed")).toHaveTextContent("null");
  });

  it.each(["expired", "unknown action", "private search query"])("does not resume an %s stored intent", async kind => {
    const intent = { action: kind === "unknown action" ? "admin" : "message", listing_id: "listing-1", initiator_id: "open-message", created_at: Date.now() - (kind === "expired" ? INTENT_TTL : 0), ...(kind === "private search query" ? { search_query: "email=private@example.com" } : {}) };
    sessionStorage.setItem(INTENT_KEY, JSON.stringify(intent)); fetchMock.mockResolvedValue(response(a)); mount();
    await waitFor(() => expect(identity()).toHaveTextContent(a.user.id));
    expect(screen.getByLabelText("resumed")).toHaveTextContent("null"); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("resumes ensure only after auth refresh renders the new identity and restores focus", async () => {
    const authenticated = deferred<Response>(); let probes = 0;
    fetchMock.mockImplementation(async path => path === "/bff/auth/session" ? ++probes === 1 ? response(anonymous) : authenticated.promise : response({ ok: true }));
    const observed: string[] = []; const done = vi.fn((ok: boolean) => observed.push(`${ok}:${identity().textContent}`));
    mount({ onResume: done }); await waitFor(() => expect(identity()).toHaveTextContent("anonymous"));
    const opener = screen.getByRole("button", { name: "Start message" }); opener.focus(); fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog"); expect(within(dialog).getByLabelText("E-mail")).toHaveFocus();
    fireEvent.change(within(dialog).getByLabelText("E-mail"), { target: { value: "synthetic@example.com" } });
    fireEvent.change(within(dialog).getByLabelText("Hasło"), { target: { value: "Synthetic-password!" } });
    fireEvent.submit(within(dialog).getByLabelText("Hasło").closest("form")!);
    await waitFor(() => expect(probes).toBe(2)); expect(done).not.toHaveBeenCalled(); expect(identity()).toHaveTextContent("anonymous");
    await act(async () => authenticated.resolve(response(a)));
    await waitFor(() => expect(identity()).toHaveTextContent(a.user.id)); expect(done).not.toHaveBeenCalled();
    await settleFrames(); expect(observed).toEqual([`true:${a.user.id}`]); expect(opener).toHaveFocus();
    expect(sessionStorage.getItem(INTENT_KEY)).toBeNull(); expect(writes()).toHaveLength(0);
  });
});

describe("real provider, immutable composer and identity changes", () => {
  it("retains a pending keyed attempt through passive focus then retries the exact body and UUID", async () => {
    let sends = 0;
    fetchMock.mockImplementation(async path => {
      if (path === "/bff/auth/session") return response(a);
      if (++sends === 1) throw new TypeError("response lost");
      return response(message, 201);
    });
    mount({ compose: true }); await makePending(); const first = JSON.parse(String(writes()[0]![1]!.body));
    await act(async () => { window.dispatchEvent(new Event("focus")); document.dispatchEvent(new Event("visibilitychange")); });
    expect(sessionCalls()).toHaveLength(1); expect(writes()).toHaveLength(1);
    expect(screen.getByLabelText("Wiadomość")).toHaveValue("Private pending text"); expect(screen.getByLabelText("Wiadomość")).toHaveAttribute("readonly");
    expect([...Object.values(sessionStorage), ...Object.values(localStorage)].join(" ")).not.toContain("Private pending text");
    fireEvent.click(screen.getByRole("button", { name: "Ponów tę samą wiadomość" })); await screen.findByText("Wiadomość wysłana");
    expect(JSON.parse(String(writes()[1]![1]!.body))).toEqual(first);
    await act(async () => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(sessionCalls()).toHaveLength(2));
  });

  it.each(["anonymous", "different account"])("explicit refresh clears pending private state for %s despite draft retention", async state => {
    let probes = 0;
    fetchMock.mockImplementation(async path => {
      if (path === "/bff/auth/session") return response(++probes === 1 ? a : state === "anonymous" ? anonymous : b);
      throw new TypeError("response lost");
    });
    mount({ compose: true }); await makePending(); fireEvent.click(screen.getByRole("button", { name: "Remember restriction" }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh identity" }));
    await waitFor(() => expect(identity()).toHaveTextContent(state === "anonymous" ? "anonymous" : b.user.id));
    expect(screen.queryByDisplayValue("Private pending text")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ponów tę самą wiadomość" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("blocked")).toBeEmptyDOMElement(); expect(writes()).toHaveLength(1);
  });

  it("real logout clears a retained draft and private composer after authoritative anonymous refresh", async () => {
    let signedOut = false;
    fetchMock.mockImplementation(async path => {
      if (path === "/bff/auth/session") return response(signedOut ? anonymous : a);
      if (path === "/bff/auth/logout") { signedOut = true; return new Response(null, { status: 204 }); }
      if (String(path).includes("/me/classifieds")) return response([]);
      throw new TypeError("response lost");
    });
    mount({ compose: true }, true); await makePending();
    fireEvent.click(screen.getByRole("button", { name: "Wyloguj się" }));
    await waitFor(() => expect(identity()).toHaveTextContent("anonymous"));
    expect(screen.queryByDisplayValue("Private pending text")).not.toBeInTheDocument(); expect(screen.queryByLabelText("Wiadomość")).not.toBeInTheDocument();
    expect(writes()).toHaveLength(1);
  });

  it("preserves identity on a transient probe failure, but removes it on an authoritative 401", async () => {
    let probes = 0;
    fetchMock.mockImplementation(async () => response(++probes === 1 ? a : { detail: "probe failed" }, probes === 1 ? 200 : probes === 2 ? 503 : 401));
    mount(); await waitFor(() => expect(identity()).toHaveTextContent(a.user.id));
    await act(async () => window.dispatchEvent(new Event("focus"))); await waitFor(() => expect(probes).toBe(2));
    expect(identity()).toHaveTextContent(a.user.id);
    await act(async () => window.dispatchEvent(new Event("focus"))); await waitFor(() => expect(probes).toBe(3));
    await waitFor(() => expect(identity()).toHaveTextContent("anonymous"));
  });

  it("does not let an older background probe restore an account after a newer explicit refresh", async () => {
    const stale = deferred<Response>(); let probes = 0;
    fetchMock.mockImplementation(async () => ++probes === 1 ? response(a) : probes === 2 ? stale.promise : response(b));
    mount(); await waitFor(() => expect(identity()).toHaveTextContent(a.user.id));
    fireEvent(window, new Event("focus")); await waitFor(() => expect(probes).toBe(2));
    fireEvent.click(screen.getByRole("button", { name: "Refresh identity" })); await waitFor(() => expect(identity()).toHaveTextContent(b.user.id));
    await act(async () => stale.resolve(response(a)));
    expect(identity()).toHaveTextContent(b.user.id);
  });
});



describe("retained draft does not override private resource authorization", () => {
  it.each([401, 403, 404])("removes the old thread and pending retry after its read returns %s", async status => {
    const conversation = { id: "thread-1", listing_id: "listing-1", status: "ACTIVE", my_side: "tenant", created_at: message.created_at, last_message_at: message.created_at };
    let reads = 0;
    fetchMock.mockImplementation(async (path, init) => {
      if (path === "/bff/auth/session") return response(a);
      if (path === "/bff/v1/conversations") return response([conversation]);
      if (path === "/bff/v1/conversations/thread-1") return ++reads === 1 ? response({ conversation, messages: [{ ...message, body: "Previously authorized private reply" }] }) : response({ detail: "No access" }, status);
      if (path === "/bff/v1/classifieds/listing-1") return response({ title: "Synthetic listing", district: null });
      if (init?.method === "POST") throw new TypeError("response lost");
      throw new Error(`Unexpected route ${String(path)}`);
    });
    render(<EngagementProvider><Probe /><ConversationWorkspace conversationId="thread-1" /></EngagementProvider>);
    await screen.findByText("Previously authorized private reply"); await makePending();
    fireEvent(window, new Event("focus"));
    await screen.findByText("Nie masz dostępu do tych danych");
    expect(screen.queryByRole("log")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("Private pending text")).not.toBeInTheDocument();
    expect(screen.queryByText("Previously authorized private reply")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ponów tę samą wiadomość" })).not.toBeInTheDocument();
    expect(sessionCalls()).toHaveLength(1); expect(writes()).toHaveLength(1);
  });
});
