import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { Composer, ConversationWorkspace, MessageItem, ReportDialog, mayReport, type Message } from "./conversations";
import type { Conversation } from "./api";
import { e } from "./copy";

const harness = vi.hoisted(() => ({
  session: { user: { id: "seeker", name: "Jan", phoneVerified: false, emailVerified: false } as { id: string; name: string; phoneVerified: boolean; emailVerified: boolean } | undefined, ready: true, ensure: vi.fn(), refresh: vi.fn(), blocked: new Set<string>(), block: vi.fn() },
  track: vi.fn(),
}));
vi.mock("./session", () => ({ useSession: () => harness.session, RequireSession: ({ children }: { children: ReactNode }) => harness.session.user ? children : <p>Logowanie wymagane</p> }));
vi.mock("./analytics", () => ({ trackEngagement: harness.track }));
const fetchMock = vi.fn<typeof fetch>();
const message: Message = { id: "message-1", body: "Odpowiedź", message_type: "USER", moderation_state: "NONE", created_at: "2026-10-19T10:00:00Z", sender_user_id: "provider", sender_organization_id: null };
const conversation: Conversation = { id: "thread-1", listing_id: "listing-1", status: "ACTIVE", my_side: "tenant", created_at: "2026-10-18T10:00:00Z", last_message_at: "2026-10-19T10:00:00Z" };
const provider: Conversation = { ...conversation, my_side: "provider", requester_user_id: "seeker", requester_display_name: "Jan K.", provider_stage: "NEW", assigned_to_user_id: null };
const response = (body: unknown, status = 200, headers?: HeadersInit) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
const bodyOf = (index: number) => JSON.parse(String(fetchMock.mock.calls[index]?.[1]?.body));
function draft(value = "Czy oferta jest aktualna?") { fireEvent.change(screen.getByLabelText(e.draft), { target: { value } }); }
function send() { fireEvent.click(screen.getByRole("button", { name: e.send })); }

beforeEach(() => {
  vi.clearAllMocks();
  harness.session.user = { id: "seeker", name: "Jan", phoneVerified: false, emailVerified: false };
  harness.session.ensure.mockResolvedValue(true);
  harness.session.blocked = new Set();
  fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value() { this.open = true; } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value() { this.open = false; } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("immutable message send", () => {
  it.each(["network", "timeout", 500, 502, 503, 504, 401, 429] as const)("retries %s with exact key/body and no automatic write", async failure => {
    if (failure === "network") fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    else if (failure === "timeout") fetchMock.mockRejectedValueOnce(new DOMException("timeout", "TimeoutError"));
    else fetchMock.mockResolvedValueOnce(response({ detail: failure === 503 ? "Temporary transaction result unavailable" : "try later" }, failure));
    fetchMock.mockResolvedValueOnce(response(message, 201));
    render(<Composer conversationId="thread-1" listingId="listing-1" />);
    draft("  Prywatna wiadomość  "); send();
    await screen.findByRole("button", { name: "Ponów tę samą wiadomość" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Ponów tę samą wiadomość" })).toBeEnabled());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText(e.draft)).toHaveAttribute("readonly");
    const original = bodyOf(0);
    expect(original).toEqual({ body: "Prywatna wiadomość", client_message_id: expect.stringMatching(/^[0-9a-f-]{36}$/) });
    fireEvent.click(screen.getByRole("button", { name: "Ponów tę samą wiadomość" }));
    await screen.findByText(e.sent);
    expect(bodyOf(1)).toEqual(original);
    expect(harness.track.mock.calls.flatMap(call => JSON.stringify(call)).join(" ")).not.toContain("Prywatna");
    expect(harness.track.mock.calls.flatMap(call => JSON.stringify(call)).join(" ")).not.toContain(original.client_message_id);
    if (failure === 401) expect(harness.session.ensure).toHaveBeenCalledWith({ action: "message", listing_id: "listing-1" }, true);
  });
  it("suppresses duplicate submits while a write is pending", async () => {
    let resolve!: (response: Response) => void;
    fetchMock.mockImplementation(() => new Promise(done => { resolve = done; }));
    render(<Composer conversationId="thread-1" />); draft();
    const form = screen.getByLabelText(e.draft).closest("form")!;
    fireEvent.submit(form); fireEvent.submit(form); fireEvent.keyDown(screen.getByLabelText(e.draft), { key: "Enter", ctrlKey: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => resolve(response(message, 201)));
    await screen.findByText(e.sent);
  });
  it("mints a fresh key only after a resolved successful attempt", async () => {
    fetchMock.mockImplementation(async () => response(message, 201));
    render(<Composer conversationId="thread-1" />); draft(); send(); await screen.findByText(e.sent);
    draft("Kolejna wiadomość"); send(); await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(bodyOf(0).client_message_id).not.toBe(bodyOf(1).client_message_id);
  });
  it("starts with a first message and never auto-sends on login", async () => {
    harness.session.user = undefined;
    const view = render(<Composer listingId="listing-1" />); draft(); send();
    await waitFor(() => expect(harness.session.ensure).toHaveBeenCalled());
    expect(fetchMock).not.toHaveBeenCalled();
    harness.session.user = { id: "seeker", name: "Jan", phoneVerified: false, emailVerified: false };
    fetchMock.mockResolvedValue(response({ conversation, messages: [message] }, 201));
    view.rerender(<Composer listingId="listing-1" />);
    expect(screen.getByLabelText(e.draft)).toHaveValue("Czy oferta jest aktualna?"); expect(fetchMock).not.toHaveBeenCalled();
    send(); await screen.findByText(e.sent);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/bff/v1/classifieds/listing-1/conversations");
  });
  it.each(["RECONTACT_BLOCKED", "CONVERSATION_CLOSED"])("ends %s without retry and preserves draft for copying", async code => {
    fetchMock.mockResolvedValue(response({ detail: `${code}: internal private reason` }, 409));
    render(<Composer listingId="listing-1" conversationId="thread-1" />); draft(); send();
    await waitFor(() => expect(screen.queryByRole("button", { name: e.send })).not.toBeInTheDocument());
    expect(screen.getByLabelText(e.draft)).toHaveAttribute("readonly");
    expect(screen.getByLabelText(e.draft)).toHaveValue("Czy oferta jest aktualna?");
    expect(screen.queryByText(/internal private/)).not.toBeInTheDocument();
    expect(screen.queryByText("Ponów tę samą wiadomość")).not.toBeInTheDocument();
    if (code === "RECONTACT_BLOCKED") expect(harness.session.block).toHaveBeenCalledWith("listing-1");
  });
  it.each(["CLOSED", "ARCHIVED"])("renders %s read-only without a new composer", status => {
    render(<Composer conversationId="thread-1" status={status} />);
    expect(screen.queryByLabelText(e.draft)).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: e.send })).not.toBeInTheDocument();
  });
  it("validates trimmed Unicode length and keeps plain Enter for newline", async () => {
    fetchMock.mockResolvedValue(response(message, 201)); render(<Composer conversationId="thread-1" />);
    draft("  "); expect(screen.getByRole("button", { name: e.send })).toBeDisabled();
    draft("a".repeat(4001)); expect(screen.getByRole("button", { name: e.send })).toBeDisabled();
    draft("🙂".repeat(4000)); expect(screen.getByRole("button", { name: e.send })).toBeEnabled();
    fireEvent.keyDown(screen.getByLabelText(e.draft), { key: "Enter" }); expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByLabelText(e.draft), { key: "Enter", metaKey: true }); await screen.findByText(e.sent);
  });
  it("drops late success and hides old drafts after account changes", async () => {
    let resolve!: (response: Response) => void;
    fetchMock.mockImplementation(() => new Promise(done => { resolve = done; }));
    const onSent = vi.fn(); const view = render(<Composer conversationId="thread-1" onSent={onSent} />); draft("Secret of seeker"); send();
    harness.session.user = { id: "different", name: "Different", phoneVerified: false, emailVerified: false };
    view.rerender(<Composer conversationId="thread-1" onSent={onSent} />);
    expect(screen.getByLabelText(e.draft)).toHaveValue("");
    await act(async () => resolve(response(message, 201)));
    expect(onSent).not.toHaveBeenCalled(); expect(screen.queryByText(e.sent)).not.toBeInTheDocument();
  });
});

describe("destination and denial isolation", () => {
  it("never reuses a pending key or old response for a different destination", async () => {
    let resolve!: (response: Response) => void;
    fetchMock.mockImplementationOnce(() => new Promise(done => { resolve = done; })).mockResolvedValue(response(message, 201));
    const onSent = vi.fn();
    const view = render(<Composer conversationId="old-thread" onSent={onSent} />); draft("Old private draft"); send();
    const first = bodyOf(0);
    view.rerender(<Composer conversationId="new-thread" onSent={onSent} />);
    expect(screen.getByLabelText(e.draft)).toHaveValue("");
    await act(async () => resolve(response(message, 201)));
    expect(onSent).not.toHaveBeenCalled();
    draft("New draft"); send(); await screen.findByText(e.sent);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/bff/v1/conversations/new-thread/messages");
    expect(bodyOf(1).client_message_id).not.toBe(first.client_message_id);
  });
  it.each([403, 404])("notifies the owning thread immediately about write access %s", async status => {
    fetchMock.mockResolvedValue(response({ detail: "private access reason" }, status));
    const onAccessLost = vi.fn(); render(<Composer conversationId="thread-1" onAccessLost={onAccessLost} />); draft(); send();
    await waitFor(() => expect(onAccessLost).toHaveBeenCalledOnce());
    expect(screen.queryByText("private access reason")).not.toBeInTheDocument();
  });
});
describe("message privacy and in-context reports", () => {
  it("allows only the other side USER message, excluding colleagues and removed/system", () => {
    expect(mayReport(message, conversation, "seeker")).toBe(true);
    expect(mayReport(message, provider, "manager")).toBe(false);
    expect(mayReport({ ...message, sender_user_id: "seeker" }, provider, "manager")).toBe(true);
    expect(mayReport({ ...message, sender_user_id: "seeker" }, conversation, "seeker")).toBe(false);
    expect(mayReport({ ...message, message_type: "SYSTEM" }, conversation, "seeker")).toBe(false);
    expect(mayReport({ ...message, moderation_state: "REMOVED" }, conversation, "seeker")).toBe(false);
  });
  it("never renders removed body or raw unknown SYSTEM code", () => {
    render(<ul><MessageItem message={{ ...message, moderation_state: "REMOVED", body: "SECRET REMOVED BODY" }} conversation={conversation} userId="seeker" onReport={vi.fn()} /><MessageItem message={{ ...message, id: "system", message_type: "SYSTEM", body: "system.private_details_123" }} conversation={conversation} userId="seeker" onReport={vi.fn()} /></ul>);
    expect(screen.getByText(e.removed)).toBeInTheDocument(); expect(screen.getByText(e.system)).toBeInTheDocument();
    expect(screen.queryByText(/SECRET|private_details/)).not.toBeInTheDocument(); expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
  it.each([200, 201])("accepts %s report with no verification wall or identity leak", async status => {
    fetchMock.mockResolvedValue(response({ id: "report-1", status: "WAITING" }, status));
    render(<ReportDialog messageId="message-1" onClose={vi.fn()} />);
    expect(screen.getAllByRole("option")).toHaveLength(6);
    fireEvent.click(screen.getByRole("button", { name: "Wyślij zgłoszenie" }));
    await screen.findByText(e.reportAccepted);
    expect(bodyOf(0)).toEqual({ target_type: "MESSAGE", target_id: "message-1", reason: "HARASSMENT", text: null });
    expect(harness.session.ensure).not.toHaveBeenCalled(); expect(screen.queryByText(/WAITING|report-1/)).not.toBeInTheDocument();
  });
  it("enforces OTHER >=20 and every reason <=2000 Unicode codepoints", async () => {
    fetchMock.mockResolvedValue(response({}, 201)); render(<ReportDialog messageId="message-1" onClose={vi.fn()} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "OTHER" } });
    const field = screen.getByLabelText(e.reportText); const button = screen.getByRole("button", { name: "Wyślij zgłoszenie" });
    fireEvent.change(field, { target: { value: "x".repeat(19) } }); expect(button).toBeDisabled();
    fireEvent.change(field, { target: { value: "x".repeat(2001) } }); expect(button).toBeDisabled();
    fireEvent.change(field, { target: { value: "🙂".repeat(20) } }); expect(button).toBeEnabled();
    fireEvent.click(button); await screen.findByText(e.reportAccepted);
    expect(JSON.stringify(harness.track.mock.calls)).not.toContain("🙂");
  });
  it.each([404, 409])("renders neutral report %s without raw reason", async status => {
    fetchMock.mockResolvedValue(response({ detail: "private moderation details" }, status)); render(<ReportDialog messageId="message-1" onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Wyślij zgłoszenie" })); await screen.findByText("Nie można zgłosić tej wiadomości"); expect(screen.queryByText(/private moderation/)).not.toBeInTheDocument();
  });
});

describe("inbox authority and refresh", () => {
  function arrange(providerMode = false) {
    harness.session.user = { id: providerMode ? "manager" : "seeker", name: "User", phoneVerified: false, emailVerified: false };
    fetchMock.mockImplementation(async input => {
      const url = String(input);
      if (url.includes("me/classifieds")) return response([{ id: "listing-1", scope: "MANAGE_MESSAGES", title: "Listing", status: "PUBLISHED" }]);
      if (url.endsWith("/conversations")) return response([providerMode ? provider : conversation]);
      if (url.endsWith("/conversations/thread-1")) return response({ conversation: providerMode ? provider : conversation, messages: [{ ...message, body: "Private thread", sender_user_id: "seeker" }] });
      if (url.endsWith("/classifieds/listing-1")) return response({ title: "Safe title", district: "District" });
      throw new Error(`unexpected endpoint ${url}`);
    });
  }
  it("enumerates MANAGE_MESSAGES and removes the thread on authority loss", async () => {
    arrange(true); render(<ConversationWorkspace provider conversationId="thread-1" />);
    await screen.findByText("Private thread"); expect(fetchMock.mock.calls.some(call => String(call[0]).includes("scope=MANAGE_MESSAGES"))).toBe(true);
    fetchMock.mockImplementation(async input => String(input).includes("me/classifieds") ? response([]) : String(input).endsWith("/conversations") ? response([]) : response({ detail: "not found" }, 404));
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(screen.queryByText("Private thread")).not.toBeInTheDocument());
    expect(screen.queryByText("Jan K.")).not.toBeInTheDocument(); expect(screen.queryByLabelText(e.draft)).not.toBeInTheDocument();
  });
  it("tenant routes never display provider projections even if inbox includes both", async () => {
    arrange(); const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (input, init) => String(input).endsWith("/conversations") ? response([conversation, { ...provider, id: "provider-thread", requester_display_name: "Private Provider Name" }]) : original(input, init));
    render(<ConversationWorkspace conversationId="thread-1" />); await screen.findByText("Private thread");
    expect(screen.queryByText("Private Provider Name")).not.toBeInTheDocument(); expect(fetchMock.mock.calls.some(call => String(call[0]).includes("me/classifieds"))).toBe(false);
  });
  it("clears old thread and active report when the read is denied on visibility refresh", async () => {
    arrange(); const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (input, init) => String(input).endsWith("/conversations/thread-1") ? response({ conversation, messages: [message] }) : original(input, init));
    render(<ConversationWorkspace conversationId="thread-1" />); await screen.findByText("Odpowiedź");
    fireEvent.click(screen.getByRole("button", { name: e.report })); expect(screen.getByRole("dialog")).toBeInTheDocument();
    fetchMock.mockImplementation(async (input, init) => String(input).endsWith("/conversations/thread-1") ? response({ detail: "not found" }, 404) : original(input, init));
    fireEvent(document, new Event("visibilitychange"));
    await waitFor(() => expect(screen.queryByText("Odpowiedź")).not.toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("uses a tombstone instead of inaccessible listing details", async () => {
    arrange(); const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (input, init) => String(input).endsWith("/classifieds/listing-1") ? response({ detail: "private address" }, 404) : original(input, init));
    render(<ConversationWorkspace />); await screen.findByText(e.unavailable);
    expect(screen.queryByText("private address")).not.toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: e.inbox })).getByRole("link")).toHaveAttribute("href", "/wiadomosci/thread-1");
  });
  it("removes a provider inbox projection after a denied thread read even if inbox snapshot is stale", async () => {
    arrange(true); render(<ConversationWorkspace provider conversationId="thread-1" />);
    await screen.findByText("Private thread");
    expect(screen.getAllByText("Jan K.").length).toBeGreaterThan(0);
    fetchMock.mockImplementation(async input => {
      const url = String(input);
      if (url.includes("me/classifieds")) return response([{ id: "listing-1", scope: "MANAGE_MESSAGES" }]);
      if (url.endsWith("/conversations")) return response([provider]);
      if (url.endsWith("/conversations/thread-1")) return response({ detail: "not found" }, 404);
      return response({ title: "Safe title", district: "District" });
    });
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(screen.queryByText("Private thread")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText("Jan K.")).not.toBeInTheDocument());
    expect(screen.queryByLabelText(e.draft)).not.toBeInTheDocument();
  });});
