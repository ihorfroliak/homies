"use client";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode, type FormEvent } from "react";
import { ApiError } from "@/api/errors";
import { ListingCard } from "@/components/listing/listing-card";
import { api, EngagementError, uncertain, type Schema } from "./api";
import { e } from "./copy";
import { limits } from "./limits";
import { trackEngagement } from "./analytics";
import { RequireSession, useSession } from "./session";
import { Empty, ErrorNotice, Modal, styles, useCountdown, useResource } from "./ui";
interface SavedContext { ids: ReadonlySet<string>; ready: boolean; error?: unknown; busy: ReadonlySet<string>; toggle: (id: string, save: boolean) => Promise<void>; reload: () => Promise<void> }
const Context = createContext<SavedContext | null>(null);
export function SavedProvider({ children }: { children: ReactNode }) {
  const { user, resumed, consume } = useSession();
  const [state, setState] = useState<{ account?: string; ids: Set<string>; ready: boolean; error?: unknown }>({ ids: new Set(), ready: false });
  const [busy, setBusy] = useState(new Set<string>());
  const inFlight = useRef(new Set<string>());
  const account = useRef(user?.id);
  const sequence = useRef(0);
  const initialRead = useRef<Promise<void> | undefined>(undefined);
  const reload = useCallback(async () => {
    const owner = user?.id; const version = ++sequence.current;
    if (!owner) return;
    const ids = new Set<string>();
    try {
      for (let offset = 0; offset < 500; offset += 100) {
        const page = await api<Schema<"SavedListingPage">>(`/v1/me/saved-listings?limit=100&offset=${offset}`);
        for (const item of page.items) ids.add(item.listing_id);
        if (offset + page.items.length >= page.total || !page.items.length) break;
      }
      if (version === sequence.current && account.current === owner) { initialRead.current = Promise.resolve(); setState({ account: owner, ids, ready: true }); }
    } catch (error) {
      if (version === sequence.current && account.current === owner) setState(previous => ({ account: owner, ids: previous.account === owner ? previous.ids : new Set(), ready: false, error }));
      throw error;
    }
  }, [user?.id]);
  useEffect(() => { account.current = user?.id; initialRead.current = reload(); void initialRead.current.catch(() => undefined); }, [reload, user?.id]);
  const toggle = useCallback(async (id: string, save: boolean) => {
    if (inFlight.current.has(id)) return;
    inFlight.current.add(id); setBusy(new Set(inFlight.current));
    const owner = account.current;
    try {
      await initialRead.current;
      if (account.current !== owner) return;
      try { await api(`/v1/me/saved-listings/${id}`, save ? "POST" : "DELETE"); }
      catch (error) {
        if (error instanceof ApiError && ["network", "timeout"].includes(error.kind)) {
          try { await api(`/v1/me/saved-listings/${id}`, save ? "POST" : "DELETE"); }
          catch (retryError) { if (uncertain(retryError) && account.current === owner) await reload(); throw retryError; }
        }
        else if (uncertain(error)) { await reload(); throw error; } else throw error;
      }
      if (account.current === owner) {
        sequence.current++;
        setState(previous => { const ids = new Set(previous.account === owner ? previous.ids : []); if (save) ids.add(id); else ids.delete(id); return { account: owner, ids, ready: true }; });
      }
    } finally { inFlight.current.delete(id); setBusy(new Set(inFlight.current)); }
  }, [reload]);
  useEffect(() => { if (user && resumed?.action === "save" && resumed.listing_id) { const id = resumed.listing_id; consume(); void toggle(id, true).catch(() => undefined); } }, [user, resumed, consume, toggle]);
  return <Context.Provider value={{ ids: state.account === user?.id ? state.ids : new Set(), error: state.account === user?.id ? state.error : undefined, ready: !user || state.account === user.id && state.ready, busy, toggle, reload }}>{children}</Context.Provider>;
}
export function useSaved() { const context = useContext(Context); if (!context) throw new Error("SavedProvider missing"); return context; }
export function SaveButton({ listingId, title, removeOnly = false, surface = "card" }: { listingId: string; title: string; removeOnly?: boolean; surface?: "card" | "rail" | "dock" | "saved" }) {
  const session = useSession(); const saved = useSaved(); const [error, setError] = useState<unknown>(); const wait = useCountdown(error);
  const pressed = saved.ids.has(listingId); const pending = saved.busy.has(listingId);
  async function act() {
    const save = !removeOnly && !pressed;
    if (!await session.ensure({ action: "save", listing_id: listingId })) return;
    setError(undefined);
    try { await saved.toggle(listingId, save); trackEngagement("save_toggled", { listing_id: listingId, action: save ? "save" : "unsave", outcome: "success", surface }); }
    catch (error) { setError(error); if (error instanceof ApiError && error.status === 401 && await session.ensure({ action: "save", listing_id: listingId }, true)) { try { await saved.toggle(listingId, save); setError(undefined); } catch (next) { setError(next); } } }
  }
  return <div className={styles.save}><button className="btn" aria-label={`${pressed || removeOnly ? e.unsave : e.save}: ${title}`} aria-pressed={pressed} aria-busy={pending} disabled={pending || wait > 0 || Boolean(session.user) && !saved.ready} onClick={() => void act()}>{pending ? e.saving : pressed || removeOnly ? e.unsave : e.save}</button><ErrorNotice error={saved.error} retry={() => { void saved.reload().catch(() => undefined); }} /><ErrorNotice error={error} />{error instanceof ApiError && error.code === "SAVED_LIMIT" && <Link href="/zapisane">{e.saved}</Link>}</div>;
}
export function SaveSearchButton({ query }: { query: string }) {
  const session = useSession(); const [open, setOpen] = useState(false);
  useEffect(() => { if (session.user && session.resumed?.action === "save_search") { session.consume(); queueMicrotask(() => setOpen(true)); } }, [session]);
  return <><button className="btn" onClick={async () => { if (await session.ensure({ action: "save_search", search_query: query })) setOpen(true); }}>{e.saveSearch}</button>{open && <Modal title={e.saveSearch} onClose={() => setOpen(false)}><SaveSearchForm query={query} /></Modal>}</>;
}
function SaveSearchForm({ query }: { query: string }) {
  const session = useSession(); const [name, setName] = useState(""); const [alerts, setAlerts] = useState(false); const [pending, setPending] = useState(false); const [error, setError] = useState<unknown>(); const [done, setDone] = useState(false); const wait = useCountdown(error);
  async function submit(event: FormEvent) { event.preventDefault(); setPending(true); setError(undefined); try { await api("/v1/me/saved-searches", "POST", { name: name.trim(), query, notifications_enabled: alerts }); setDone(true); } catch (error) { setError(error); if (error instanceof ApiError && error.status === 401) await session.ensure({ action: "save_search", search_query: query }, true); } finally { setPending(false); } }
  if (done) return <p role="status">{e.saved} <Link href="/zapisane#wyszukiwania">{e.searches}</Link></p>;
  return <form className={styles.form} onSubmit={submit}><label>{e.searchName}<input required maxLength={limits.searchName} value={name} onChange={event => setName(event.target.value)} /></label><label><input type="checkbox" checked={alerts} onChange={event => setAlerts(event.target.checked)} />{e.alerts}</label><ErrorNotice error={error} />{error instanceof EngagementError && error.location && <Link href={`/zapisane?wyszukiwanie=${error.location}#wyszukiwania`}>{e.openExisting}</Link>}<button className="btn btn--primary" disabled={pending || wait > 0 || !name.trim()}>{e.save}</button></form>;
}
export function SavedPage() { return <div className={`container ${styles.page}`}><h1>{e.saved}</h1><RequireSession><SavedContent /></RequireSession></div>; }
function SavedContent() {
  const { user } = useSession(); const saved = useSaved(); const [offset, setOffset] = useState(0);
  const page = useResource<Schema<"SavedListingPage">>(`/v1/me/saved-listings?limit=24&offset=${offset}`, user?.id);
  // A successful toggle invalidates the visible page, including tombstone removal.
  const reloadPage = page.reload;
  useEffect(() => { queueMicrotask(reloadPage); }, [saved.ids, reloadPage]);
  return <><ErrorNotice error={page.error} retry={page.reload} />{page.loading && <p aria-busy="true">{e.loading}</p>}<ul className={styles.list}>{page.data?.items.map(item => <li key={item.saved_id}>{item.availability_status === "AVAILABLE" && item.listing ? <ListingCard listing={item.listing} /> : <article className={styles.card}><h2>{e.unavailable}</h2><time dateTime={item.saved_at}>{new Intl.DateTimeFormat("pl-PL").format(new Date(item.saved_at))}</time><SaveButton listingId={item.listing_id} title={e.unavailable} removeOnly /></article>}</li>)}</ul>{page.data?.total === 0 && <Empty>{e.emptySaved}</Empty>}<div className={styles.actions}>{offset > 0 && <button className="btn" onClick={() => setOffset(offset - 24)}>{e.previous}</button>}{page.data && offset + 24 < page.data.total && <button className="btn" onClick={() => setOffset(offset + 24)}>{e.nextPage}</button>}</div><SavedSearches /></>;
}
function SavedSearches() {
  const { user, ensure } = useSession(); const list = useResource<Schema<"SavedSearchList">>("/v1/me/saved-searches?limit=50", user?.id); const [selected, setSelected] = useState<string>(); const [error, setError] = useState<unknown>(); const [busy, setBusy] = useState<string>();
  const activeSearch = list.data?.items.find(item => item.id === selected && item.query_state === "VALID");
  const matches = useResource<Schema<"ClassifiedPage">>(activeSearch ? `/v1/me/saved-searches/${activeSearch.id}/matches?limit=100` : null, user?.id);
  async function update(item: Schema<"SavedSearchOut">, patch?: Record<string, unknown>) { setBusy(item.id); setError(undefined); try { await api(`/v1/me/saved-searches/${item.id}`, patch ? "PATCH" : "DELETE", patch ? { ...patch, expected_version: item.version } : undefined); list.reload(); } catch (error) { setError(error); list.reload(); if (error instanceof ApiError && error.status === 401) await ensure({ action: "save_search" }, true); } finally { setBusy(undefined); } }
  return <section id="wyszukiwania"><h2>{e.searches}</h2><ErrorNotice error={list.error} retry={list.reload} /><ErrorNotice error={error} />{list.data?.items.length === 0 && <Empty>{e.emptySearches}</Empty>}<ul className={styles.list}>{list.data?.items.map(item => <li className={styles.card} key={item.id}><h3>{item.name}</h3>{item.query_state === "INVALID" ? <p>{e.invalidSearch}</p> : <button className="btn" onClick={() => setSelected(item.id)}>{e.matches}</button>}<div className={styles.actions}><label><input type="checkbox" checked={item.notifications_enabled} disabled={busy === item.id} onChange={event => void update(item, { notifications_enabled: event.target.checked })} />{e.alerts}</label><button className="btn" disabled={busy === item.id} onClick={() => void update(item, { status: item.status === "active" ? "paused" : "active" })}>{item.status === "active" ? e.pause : e.resume}</button><button className="btn" disabled={busy === item.id} onClick={() => void update(item)}>{e.remove}</button></div></li>)}</ul>{activeSearch && <section><h3>{e.matches}</h3><ErrorNotice error={matches.error} retry={matches.reload} />{matches.data?.items.map(listing => <ListingCard key={listing.id} listing={listing} />)}{matches.data?.total === 0 && <p>{e.emptyMatches}</p>}</section>}</section>;
}
