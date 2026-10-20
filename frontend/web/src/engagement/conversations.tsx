"use client";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError } from "@/api/errors";
import { api, retrySend, type Conversation, type Listing, type Schema } from "./api";
import { e, reasons } from "./copy";
import { trackEngagement } from "./analytics";
import { RequireSession, useSession } from "./session";
import { ErrorNotice, Modal, styles, useCountdown, useResource } from "./ui";
import c from "./conversations.module.css";

export type ConversationDetail = Schema<"ConversationDetail">;
export type Message = Schema<"MessageOut">;
type SendResult = ConversationDetail | Message;
type Attempt = { body: string; client_message_id: string; account: string; path: string };
const text = {
  active: "Rozmowa aktywna", providerInbox: "Rozmowy w panelu", chooseThread: "Wybierz rozmowę", you: "Ty", other: "Rozmówca", owner: "Właściciel lub opiekun oferty", reportUnavailable: "Nie można zgłosić tej wiadomości", retryMessage: "Ponów tę samą wiadomość", tooLong: "Wiadomość może mieć maksymalnie 4000 znaków.", pending: "Trwa ustalanie wyniku wysyłki. Treść pozostaje niezmienna do rozstrzygnięcia.", newDraft: "Edytuj niewysłaną wiadomość", search: "Przejdź do wyszukiwania", noProvider: "Nie masz ofert z dostępem do rozmów.", updated: "Rozmowa odświeżona", refresh: "Odśwież rozmowę", reportSend: "Wyślij zgłoszenie", awaiting: "Wysłanie wymaga ponownego potwierdzenia po zalogowaniu.",
} as const;
const statusText = (status: string) => status === "ACTIVE" ? text.active : status === "CLOSED" ? e.closed : status === "ARCHIVED" ? e.archived : e.noAccess;

/** The unresolved attempt owns its immutable body, destination and UUID. No storage. */
type ComposerProps = {
  listingId?: string; conversationId?: string; status?: string; my_side?: "tenant" | "provider"; onSent?: (result: SendResult) => void; onClose?: () => void; onAccessLost?: () => void;
};
export function Composer(props: ComposerProps) { return <ComposerScope key={`${props.conversationId ?? ""}:${props.listingId ?? ""}`} {...props} />; }
function ComposerScope({ listingId, conversationId, status = "ACTIVE", my_side = "tenant", onSent, onClose, onAccessLost }: ComposerProps) {
  const session = useSession();
  const current = useRef(session); useEffect(() => { current.current = session; }, [session]);
  const [state, setState] = useState<{ owner?: string; draft: string; attempt?: Attempt; error?: unknown; final?: boolean; notice?: string }>({ draft: "" });
  const [sending, setSending] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const accountChanged = Boolean(state.owner && state.owner !== session.user?.id);
  const visible = accountChanged ? { draft: "" } : state;
  const remaining = useCountdown(visible.error);
  const textareaId = useId();
  const hintId = useId();
  const blocked = Boolean(listingId && session.blocked.has(listingId)) || visible.error instanceof ApiError && visible.error.code === "RECONTACT_BLOCKED";
  const closed = status !== "ACTIVE" || visible.error instanceof ApiError && visible.error.code === "CONVERSATION_CLOSED";
  const draft = visible.draft;
  const length = [...draft.trim()].length;
  const valid = length > 0 && length <= 4000;
  const pending = visible.attempt;
  const retainDraft = session.retainDraft;
  useEffect(() => { if (draft || pending) return retainDraft?.(); }, [draft, pending, retainDraft]);

  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (busy.current || remaining || blocked || closed || !valid || visible.final) return;
    if (!session.user) { await session.ensure({ action: "message", listing_id: listingId }); return; }
    const account = session.user.id;
    const path = conversationId ? `/v1/conversations/${encodeURIComponent(conversationId)}/messages` : listingId ? `/v1/classifieds/${encodeURIComponent(listingId)}/conversations` : undefined;
    if (!path) return;
    const attempt = pending ?? { body: draft.trim(), client_message_id: crypto.randomUUID(), account, path };
    if (attempt.account !== account) return;
    const track = (outcome: string) => conversationId ? trackEngagement("message_send_submitted", { outcome, side: my_side, retried: Boolean(pending) }, my_side === "provider" ? "/panel/leady/[id]" : "/wiadomosci/[id]") : trackEngagement("conversation_start_submitted", { listing_id: listingId, outcome });
    busy.current = true; setSending(true);
    setState({ owner: account, draft, attempt });
    try {
      const result = await api<SendResult>(attempt.path, "POST", { body: attempt.body, client_message_id: attempt.client_message_id });
      if (!mounted.current || current.current.user?.id !== account) return;
      track("success");
      setState({ owner: account, draft: "", notice: e.sent });
      onSent?.(result);
    } catch (error) {
      if (!mounted.current || current.current.user?.id !== account) return;
      const retry = retrySend(error);
      track(retry ? "unknown" : "refused");
      setState({ owner: account, draft, attempt: retry ? attempt : undefined, error, final: !retry });
      if (error instanceof ApiError && error.code === "RECONTACT_BLOCKED" && listingId) { current.current.block(listingId); trackEngagement("engagement_refused", { surface: "conversation", code: "RECONTACT_BLOCKED" }); }
      if (error instanceof ApiError && (error.status === 403 || error.status === 404)) onAccessLost?.();
      if (error instanceof ApiError && error.status === 401) {
        await current.current.ensure({ action: "message", listing_id: listingId }, true); // AuthForm refreshes; another explicit send replays this key.
      }
    } finally { busy.current = false; if (mounted.current) setSending(false); }
  }
  return <form className={styles.form} onSubmit={send} aria-busy={sending}>
    {closed && <p role="status">{statusText(status === "ACTIVE" ? "CLOSED" : status)}</p>}
    {blocked && <p role="alert">{e.conversationUnavailable}</p>}
    {(!closed && !blocked || draft) && <><label htmlFor={textareaId}>{e.draft}</label><textarea id={textareaId} value={draft} readOnly={Boolean(pending) || sending || closed || blocked || Boolean(visible.final)} aria-describedby={hintId} onChange={event => setState({ owner: session.user?.id, draft: event.target.value })} onKeyDown={event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void send(); } }} /></>}
    <p id={hintId} className={styles.muted}>{closed || blocked ? e.copiedDraft : pending ? text.pending : e.privacyHint}{length >= 3600 && <span> {length}/4000</span>}</p>
    {length > 4000 && <p role="alert">{text.tooLong}</p>}
    {pending && !sending && <p role="status">{e.unknownSend}</p>}
    <ErrorNotice error={visible.error} />
    {visible.notice && <p role="status">{visible.notice}</p>}
    {!closed && !blocked && <div className={styles.actions}>
      {!visible.final && <button className="btn btn--primary" disabled={sending || remaining > 0 || !valid || !listingId && !conversationId}>{sending ? e.sending : pending ? text.retryMessage : e.send}</button>}
      {visible.final && <button type="button" className="btn" onClick={() => setState({ owner: session.user?.id, draft })}>{text.newDraft}</button>}
      {onClose && <button type="button" className="btn" onClick={onClose}>{e.close}</button>}
    </div>}
  </form>;
}

/** Provider colleagues are the same side, even if their user id differs. */
export function mayReport(message: Message, conversation: Conversation, userId: string): boolean {
  if (message.message_type !== "USER" || message.moderation_state === "REMOVED" || !message.sender_user_id || message.sender_user_id === userId) return false;
  return conversation.my_side === "tenant" || "requester_user_id" in conversation && message.sender_user_id === conversation.requester_user_id;
}
export function MessageItem({ message, conversation, userId, onReport }: { message: Message; conversation: Conversation; userId: string; onReport: (message: Message) => void }) {
  const removed = message.moderation_state === "REMOVED";
  const system = message.message_type === "SYSTEM";
  const body = removed ? e.removed : system ? message.body === "system.conversation_closed_by_homies" ? e.closed : e.system : message.message_type === "USER" ? message.body : e.system;
  const who = system ? "Homies" : message.sender_user_id === userId ? text.you : conversation.my_side === "provider" && "requester_user_id" in conversation && message.sender_user_id === conversation.requester_user_id ? conversation.requester_display_name : text.other;
  return <li className={styles.card}>
    <p className={styles.muted}>{who} · <time dateTime={message.created_at}>{formatTime(message.created_at)}</time></p>
    <p className={`${styles.message} ${removed || system ? c.system : ""}`}>{body}</p>
    {mayReport(message, conversation, userId) && <button className="btn" onClick={() => onReport(message)}>{e.report}</button>}
  </li>;
}
function formatTime(value: string) { return new Intl.DateTimeFormat("pl-PL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)); }

export function ReportDialog({ messageId, onClose, onAccessLost }: { messageId: string; onClose: () => void; onAccessLost?: () => void }) {
  const session = useSession();
  const account = session.user?.id;
  const identity = useRef(account); useEffect(() => { identity.current = account; }, [account]);
  const [reason, setReason] = useState<keyof typeof reasons>("HARASSMENT");
  const [body, setBody] = useState("");
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const lock = useRef(false);
  const remaining = useCountdown(error);
  const length = [...body.trim()].length;
  const valid = length <= 2000 && (reason !== "OTHER" || length >= 20);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (lock.current || remaining || !valid) return;
    if (!session.user) { await session.ensure({ action: "report", message_id: messageId }); return; }
    lock.current = true; setPending(true); setError(undefined);
    try { await api("/v1/reports", "POST", { target_type: "MESSAGE", target_id: messageId, reason, text: body.trim() || null }); if (identity.current === account) { trackEngagement("message_report_submitted", { reason, outcome: "success" }, "/wiadomosci/[id]"); setBody(""); setAccepted(true); } }
    catch (error) { if (identity.current === account) { trackEngagement("message_report_submitted", { reason, outcome: "refused" }, "/wiadomosci/[id]"); setError(error); if (error instanceof ApiError && (error.status === 403 || error.status === 404)) onAccessLost?.(); } }
    finally { lock.current = false; setPending(false); }
  }
  return <Modal title={e.report} onClose={onClose} initialFocus="select">
    {accepted ? <p role="status">{e.reportAccepted}</p> : <form className={styles.form} onSubmit={submit} aria-busy={pending}>
      <label>{e.reason}<select value={reason} onChange={event => setReason(event.target.value as keyof typeof reasons)} disabled={pending}>{Object.entries(reasons).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>{e.reportText}<textarea value={body} onChange={event => setBody(event.target.value)} disabled={pending} /></label>
      {reason === "OTHER" && <p>{e.otherHint}</p>}<p className={styles.muted}>{length}/2000 · {e.privacyHint}</p>
      {error instanceof ApiError && (error.status === 404 || error.status === 409) ? <p role="alert">{text.reportUnavailable}</p> : <ErrorNotice error={error} />}
      <button className="btn btn--primary" disabled={pending || remaining > 0 || !valid}>{pending ? e.sending : text.reportSend}</button>
    </form>}
  </Modal>;
}

function ListingLabel({ listingId, href = false }: { listingId: string | null; href?: boolean }) {
  const { data } = useResource<Listing>(listingId ? `/v1/classifieds/${encodeURIComponent(listingId)}` : null);
  if (!data) return <span>{e.unavailable}</span>;
  const label = <>{data.title}{data.district && <span className={styles.muted}> · {data.district}</span>}</>;
  return href && listingId ? <Link href={`/oferta/${encodeURIComponent(listingId)}`}>{label}</Link> : label;
}

export function ConversationWorkspace({ provider = false, conversationId }: { provider?: boolean; conversationId?: string }) {
  const { user } = useSession();
  return <RequireSession>{user && <Workspace key={`${user.id}:${provider}`} userId={user.id} provider={provider} conversationId={conversationId} />}</RequireSession>;
}
function Workspace({ userId, provider, conversationId }: { userId: string; provider: boolean; conversationId?: string }) {
  const [denied, setDenied] = useState<ReadonlySet<string>>(new Set());
  const deny = useCallback((id: string) => setDenied(previous => new Set([...previous, id])), []);
  const inbox = useResource<Conversation[]>("/v1/conversations", userId);
  const managed = useResource<Schema<"ProviderListingOut">[]>(provider ? "/v1/me/classifieds?scope=MANAGE_MESSAGES" : null, userId);
  const base = provider ? "/panel/leady" : "/wiadomosci";
  const allowed = new Set(managed.data?.map(row => row.id));
  const rows = (inbox.data ?? []).filter(row => !denied.has(row.id) && row.my_side === (provider ? "provider" : "tenant") && (!provider || Boolean(row.listing_id && allowed.has(row.listing_id)))).sort((a, b) => (b.last_message_at ?? b.created_at).localeCompare(a.last_message_at ?? a.created_at));
  const error = inbox.error ?? (provider ? managed.error : undefined);
  const loading = inbox.loading || provider && managed.loading;
  const refresh = () => { inbox.reload(); managed.reload(); };
  const selected = rows.find(row => row.id === conversationId);
  return <main className={`container ${styles.page}`}>
    <h1>{provider ? text.providerInbox : e.inbox}</h1>
    <div className={styles.actions}><Link href={provider ? "/wiadomosci" : "/ogladania"}>{provider ? e.seeker : e.myViewings}</Link>{provider && <Link href="/panel/ogladania">{e.providerViewings}</Link>}</div>
    <ErrorNotice error={error} retry={refresh} />
    {loading && <p aria-busy="true">{e.loading}</p>}
    {!error && !loading && <div className={styles.split}>
      <nav aria-label={provider ? text.providerInbox : e.inbox} className={conversationId && selected ? c.inboxOnThread : undefined}>
        {rows.length ? <ul className={styles.list}>{rows.map(row => <li key={row.id} className={styles.card}><Link href={`${base}/${encodeURIComponent(row.id)}`} aria-current={row.id === conversationId ? "page" : undefined}><ListingLabel listingId={row.listing_id} />{provider && "requester_display_name" in row && <p>{row.requester_display_name}</p>}<p>{statusText(row.status)}</p><time dateTime={row.last_message_at ?? row.created_at}>{formatTime(row.last_message_at ?? row.created_at)}</time></Link></li>)}</ul> : <p>{provider && !managed.data?.length ? text.noProvider : e.emptyInbox} {!provider && <Link href="/szukaj">{text.search}</Link>}</p>}
      </nav>
      {conversationId ? selected ? <Thread key={conversationId} conversation={selected} userId={userId} base={base} onChanged={refresh} onDenied={deny} /> : <p role="status">{e.noAccess}</p> : rows.length > 0 && <p>{text.chooseThread}</p>}
    </div>}
  </main>;
}
function Thread({ conversation, userId, base, onChanged, onDenied }: { conversation: Conversation; userId: string; base: string; onChanged: () => void; onDenied: (id: string) => void }) {
  const resource = useResource<ConversationDetail>(`/v1/conversations/${encodeURIComponent(conversation.id)}`, userId);
  const [report, setReport] = useState<string>();
  const [notice, setNotice] = useState("");
  const denial = resource.error instanceof ApiError && [401, 403, 404].includes(resource.error.status ?? 0);
  useEffect(() => { if (denial) onDenied(conversation.id); }, [denial, onDenied, conversation.id]);
  const data = resource.data;
  const accessible = data && data.conversation.my_side === conversation.my_side;
  const refresh = () => { resource.reload(); onChanged(); };
  if (resource.error) return <section><Link href={base}>{e.back}</Link><ErrorNotice error={resource.error} retry={refresh} /></section>;
  if (!accessible) return <p aria-busy="true">{e.loading}</p>;
  const messages = [...data.messages].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
  const reportMessage = messages.find(message => message.id === report && mayReport(message, data.conversation, userId));
  return <section aria-label={e.inbox}>
    <Link href={base} className={c.mobileBack}>{e.back}</Link>
    <h2><ListingLabel listingId={data.conversation.listing_id} href /></h2>
    {data.conversation.my_side === "provider" && "requester_display_name" in data.conversation && <p>{data.conversation.requester_display_name}</p>}
    <p>{statusText(data.conversation.status)}</p>
    <button className="btn" onClick={refresh}>{text.refresh}</button>
    <div role="log" aria-label={e.inbox} aria-live="off"><ol className={styles.list}>{messages.map(message => <MessageItem key={message.id} message={message} conversation={data.conversation} userId={userId} onReport={item => setReport(item.id)} />)}</ol></div>
    <p role="status">{notice}</p>
    <Composer listingId={data.conversation.listing_id ?? undefined} conversationId={data.conversation.id} status={data.conversation.status} my_side={data.conversation.my_side} onAccessLost={() => onDenied(conversation.id)} onSent={() => { setNotice(e.sent); refresh(); }} />
    {reportMessage && <ReportDialog key={reportMessage.id} messageId={reportMessage.id} onClose={() => setReport(undefined)} onAccessLost={() => onDenied(conversation.id)} />}
  </section>;
}
