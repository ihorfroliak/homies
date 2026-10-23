"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "@/api/errors";
import { api, uncertain, type Schema, type Viewing } from "./api";
import { trackEngagement } from "./analytics";
import { e } from "./copy";
import { limits } from "./limits";
import { RequireSession, useSession } from "./session";
import { Empty, ErrorNotice, Modal, styles, useCountdown, useResource } from "./ui";
import { slotGroups, viewingActions, viewingLabel, viewingLabels, viewingTime } from "./viewing-model";

type PickerProps = { listingId: string; initialSlot?: string; onClose: () => void; onMessage: () => void };
export function ViewingPicker(props: PickerProps) {
  const { user } = useSession();
  const [identity, setIdentity] = useState({ owner: user?.id, generation: 0 });
  // Guest authentication retains the selected public instant. Leaving an
  // authenticated identity resets private form state before children render.
  if (identity.owner !== user?.id) setIdentity({ owner: user?.id, generation: identity.generation + (identity.owner ? 1 : 0) });
  return <ViewingPickerScope key={`${props.listingId}:${identity.generation}`} {...props} />;
}
function ViewingPickerScope({ listingId, initialSlot, onClose, onMessage }: PickerProps) {
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const session = useSession(); const [days, setDays] = useState(14); const [selected, setSelected] = useState(initialSlot ?? ""); const [confirm, setConfirm] = useState(false); const [suspended, setSuspended] = useState(false); const [count, setCount] = useState(1); const [note, setNote] = useState(""); const [pending, setPending] = useState(false); const [error, setError] = useState<unknown>(); const [result, setResult] = useState<Viewing>(); const [invalidSlot, setInvalidSlot] = useState(false);
  const slots = useResource<Schema<"ViewingSlotsOut">>(`/v1/classifieds/${listingId}/viewing-slots?days=${days}`); const wait = useCountdown(error);
  const validSelection = Boolean(selected && slots.data?.slots.includes(selected));
  async function next() {
    if (!validSelection) return;
    if (!session.user) {
      setSuspended(true);
      const authenticated = await session.ensure({ action: "viewing", listing_id: listingId, starts_at: selected });
      if (!active.current) return;
      setSuspended(false); if (!authenticated) return;
    }
    setPending(true); setError(undefined);
    try { const fresh = await api<Schema<"ViewingSlotsOut">>(`/v1/classifieds/${listingId}/viewing-slots?days=${days}`); slots.reload(); if (!fresh.slots.includes(selected)) { setSelected(""); setInvalidSlot(true); } else { setInvalidSlot(false); setConfirm(true); } } catch (error) { setError(error); } finally { setPending(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(undefined);
    try { const created = await api<Viewing>(`/v1/classifieds/${listingId}/viewings`, "POST", { starts_at: selected, attendee_count: count, note: note.trim() || null }); if (!active.current) return; setResult(created); trackEngagement("viewing_request_submitted", { listing_id: listingId, outcome: "success", attendees_bucket: count > 3 ? "4plus" : String(count) }); }
    catch (error) {
      if (!active.current) return;
      setError(error);
      trackEngagement("viewing_request_submitted", { listing_id: listingId, outcome: uncertain(error) ? "unknown" : "refused", attendees_bucket: count > 3 ? "4plus" : String(count) });
      if (uncertain(error)) {
        try { const existing = await api<Viewing[]>("/v1/me/viewings"); if (!active.current) return; const found = existing.find(item => item.listing_id === listingId && Date.parse(item.starts_at) === Date.parse(selected) && ["REQUESTED", "CONFIRMED"].includes(item.status)); if (found) { setResult(found); setError(undefined); } } catch { /* Preserve uncertainty; never blindly repeat. */ }
      }
      if (error instanceof ApiError) {
        if (error.code === "RECONTACT_BLOCKED") { session.block(listingId); trackEngagement("engagement_refused", { surface: "viewing", code: error.code }); }
        if (["SLOT_NOT_OFFERED", "SLOT_FULL"].includes(error.code ?? "")) { slots.reload(); setConfirm(false); setSelected(""); setInvalidSlot(true); }
        if (error.status === 401) { setSuspended(true); await session.ensure({ action: "viewing", listing_id: listingId, starts_at: selected }, true); setSuspended(false); setConfirm(false); slots.reload(); }
      }
    } finally { setPending(false); }
  }
  if (suspended) return null;
  return <Modal title={result ? e.myViewings : confirm ? e.confirmViewing : e.selectSlot} onClose={onClose}>
    {result ? <div role="status"><p>{viewingLabels[result.status]}</p><p>{viewingTime(result.starts_at, slots.data?.timezone)}</p><Link href="/ogladania">{e.myViewings}</Link></div> : session.blocked.has(listingId) ? <p role="status">{e.viewingUnavailable}</p> : confirm ? <form onSubmit={submit} className={styles.form}><p>{viewingTime(selected, slots.data?.timezone)} · {slots.data?.duration_minutes} min</p><label>{e.attendees}<input type="number" min={limits.attendeesMin} max={limits.attendeesMax} required value={count} onChange={event => setCount(Number(event.target.value))} /></label><label>{e.note}<textarea maxLength={limits.viewingNote} value={note} onChange={event => setNote(event.target.value)} /></label><p>{e.privacyHint}</p><ErrorNotice error={error} />{error instanceof ApiError && error.code === "VIEWING_ALREADY_BOOKED" && <Link href="/ogladania">{e.seeViewing}</Link>}{uncertain(error) && <Link href="/ogladania">{e.myViewings}</Link>}<div className={styles.actions}><button type="button" className="btn" onClick={() => setConfirm(false)}>{e.back}</button><button className="btn btn--primary" disabled={pending || wait > 0 || uncertain(error)}>{e.confirmViewing}</button></div></form> : <div className={styles.form}>
      <ErrorNotice error={slots.error} retry={slots.reload} /><ErrorNotice error={error} />{invalidSlot && <p role="status" tabIndex={-1}>{e.changedSlot}</p>}{slots.loading && <p aria-busy="true">{e.loading}</p>}
      {slots.data?.duration_minutes === null ? <div><p>{e.noSettings}</p><button className="btn" onClick={onMessage}>{e.message}</button></div> : slots.data?.slots.length === 0 ? <p>{e.noSlots}</p> : null}
      {slots.data?.timezone && <SlotChoices slots={slots.data.slots} timezone={slots.data.timezone} duration={slots.data.duration_minutes ?? 0} selected={selected} onSelect={instant => { setSelected(instant); setInvalidSlot(false); const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone: slots.data!.timezone!, hour: "2-digit", hourCycle: "h23" }).format(new Date(instant))); trackEngagement("viewing_slot_selected", { listing_id: listingId, days_ahead_bucket: Date.parse(instant) - Date.now() > 7 * 86400000 ? "later" : "week", hour_bucket: hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening", authenticated: Boolean(session.user) }); }} />}
      {days < 31 && <button className="btn" onClick={() => setDays(31)}>{e.nextDays}</button>}<button className="btn btn--primary" disabled={!validSelection || pending || wait > 0} onClick={() => void next()}>{e.next}</button>
    </div>}
  </Modal>;
}

export function SlotChoices({ slots, timezone, duration, selected, onSelect }: { slots: string[]; timezone: string; duration: number; selected: string; onSelect: (instant: string) => void }) {
  const groups = [...slotGroups(slots, timezone)]; const [day, setDay] = useState("");
  const active = groups.some(([key]) => key === day) ? day : groups[0]?.[0];
  const time = (instant: number) => new Intl.DateTimeFormat("pl-PL", { timeZone: timezone, hour: "2-digit", minute: "2-digit" }).format(new Date(instant));
  return <div><div className={styles.dayTabs} role="tablist" aria-label={e.selectSlot}>{groups.map(([key], index) => <button type="button" role="tab" id={`day-${index}`} aria-controls={`slots-${index}`} aria-selected={active === key} tabIndex={active === key ? 0 : -1} className="btn" key={key} onClick={() => setDay(key)} onKeyDown={event => { const next = event.key === "ArrowRight" ? (index + 1) % groups.length : event.key === "ArrowLeft" ? (index + groups.length - 1) % groups.length : event.key === "Home" ? 0 : event.key === "End" ? groups.length - 1 : undefined; if (next !== undefined) { event.preventDefault(); setDay(groups[next]![0]); document.getElementById(`day-${next}`)?.focus(); } }}>{key}</button>)}</div>
    <div className={styles.slots}>{groups.map(([key, instants], index) => <fieldset key={key} id={`slots-${index}`} className={key === active ? styles.activeDay : styles.otherDay}><legend>{key}</legend><div role="radiogroup" aria-label={key}>{instants.map(instant => <label key={instant}><input type="radio" name="viewing-slot" checked={selected === instant} onChange={() => onSelect(instant)} value={instant} />{time(Date.parse(instant))}–{time(Date.parse(instant) + duration * 60000)}</label>)}</div></fieldset>)}</div></div>;
}
export function ContextSwitch({ provider = false }: { provider?: boolean }) {
  const { user } = useSession();
  const messages = useResource<Schema<"ProviderListingOut">[]>(user ? "/v1/me/classifieds?scope=MANAGE_MESSAGES" : null, user?.id);
  const viewings = useResource<Schema<"ProviderListingOut">[]>(user ? "/v1/me/classifieds?scope=MANAGE_VIEWINGS" : null, user?.id);
  if (provider) return <nav className={styles.actions} aria-label={e.seeker}><Link href="/wiadomosci">{e.seeker}</Link>{Boolean(messages.data?.length) && <Link href="/panel/leady">{e.inbox}</Link>}{Boolean(viewings.data?.length) && <Link href="/panel/ogladania">{e.providerViewings}</Link>}</nav>;
  return messages.data?.length || viewings.data?.length ? <Link href={messages.data?.length ? "/panel/leady" : "/panel/ogladania"}>{e.panel}</Link> : null;
}
export function ViewingsPage({ provider = false }: { provider?: boolean }) { return <div className={`container ${styles.page}`}><h1>{provider ? e.providerViewings : e.myViewings}</h1><RequireSession><ContextSwitch provider={provider} />{provider ? <ProviderViewings /> : <MyViewings />}</RequireSession></div>; }
function MyViewings() {
  const { user } = useSession(); const viewings = useResource<Viewing[]>("/v1/me/viewings", user?.id);
  return <><ErrorNotice error={viewings.error} retry={viewings.reload} />{viewings.loading && <p>{e.loading}</p>}{viewings.data?.length === 0 && <Empty>{e.emptyViewings}</Empty>}<ul className={styles.list}>{viewings.data?.map(viewing => <li key={viewing.id}><ViewingRow viewing={viewing} reload={viewings.reload} /></li>)}</ul></>;
}
function ProviderViewings() {
  const { user } = useSession(); const listings = useResource<Schema<"ProviderListingOut">[]>("/v1/me/classifieds?scope=MANAGE_VIEWINGS", user?.id);
  return <><ErrorNotice error={listings.error} retry={listings.reload} />{listings.loading && <p>{e.loading}</p>}{listings.data?.length === 0 && <Empty>{e.emptyProvider}</Empty>}{listings.data?.map(listing => <ProviderListingViewings key={listing.id} id={listing.id} title={listing.title} />)}</>;
}
function ProviderListingViewings({ id, title }: { id: string; title: string }) {
  const { user } = useSession(); const rows = useResource<Schema<"ProviderViewingOut">[]>(`/v1/classifieds/${id}/viewings`, user?.id);
  if (rows.error instanceof ApiError && rows.error.status === 404) return <p>{e.noAccess}</p>;
  return <section><h2>{title}</h2><ErrorNotice error={rows.error} retry={rows.reload} />{rows.data?.length === 0 && <Empty>{e.emptyProvider}</Empty>}<ul className={styles.list}>{rows.data?.map(viewing => <li key={viewing.id}><ViewingRow viewing={viewing} provider reload={rows.reload} /></li>)}</ul></section>;
}
export function ViewingRow({ viewing, provider = false, reload }: { viewing: Viewing; provider?: boolean; reload: () => void }) {
  const session = useSession(); const [now, setNow] = useState(() => Date.now()); const [error, setError] = useState<unknown>(); const [pending, setPending] = useState(false); const [cancel, setCancel] = useState(false); const [gone, setGone] = useState(false);
  const listing = useResource<Schema<"ClassifiedOut">>(`/v1/classifieds/${viewing.listing_id}`); const schedule = useResource<Schema<"ViewingSlotsOut">>(`/v1/classifieds/${viewing.listing_id}/viewing-slots`);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const wait = useCountdown(error); const actions = viewingActions(viewing, provider, now);
  async function act(action: string) {
    setPending(true); setError(undefined); setCancel(false);
    try { await api(`/v1/viewings/${viewing.id}/${action === "COMPLETED" || action === "NO_SHOW" ? "outcome" : action}`, "POST", action === "COMPLETED" || action === "NO_SHOW" ? { outcome: action } : undefined); reload(); if (action === "cancel") trackEngagement("viewing_cancel_submitted", { outcome: "success" }, provider ? "/panel/ogladania" : "/ogladania"); }
    catch (error) { setError(error); reload(); if (error instanceof ApiError && error.status === 404) setGone(true); if (error instanceof ApiError && error.status === 401) await session.ensure({ action: "account" }, true); }
    finally { setPending(false); }
  }
  if (gone) return <p role="status">{e.noAccess}</p>;
  const names: Record<string, string> = { confirm: e.confirm, decline: e.decline, cancel: e.cancelViewing, COMPLETED: e.complete, NO_SHOW: e.noShow };
  return <article className={styles.card}><h3>{listing.data?.title ?? e.unavailable}</h3><p><time dateTime={viewing.starts_at}>{viewingTime(viewing.starts_at, schedule.data?.timezone)}</time></p><p role="status">● {viewingLabel(viewing, now)}</p>{provider && "requester_display_name" in viewing && <><p>{viewing.requester_display_name || e.requester}</p><p>{viewing.attendee_count} · {e.attendees}</p><p>{viewing.requester_note}</p></>}<ErrorNotice error={error} /><div className={styles.actions}>{actions.map(action => <button key={action} className="btn" aria-label={`${names[action]}: ${viewingTime(viewing.starts_at, schedule.data?.timezone)}`} disabled={pending || wait > 0} onClick={() => action === "cancel" ? setCancel(true) : void act(action)}>{names[action]}</button>)}{viewing.status === "DECLINED" && !provider && <Link href={`/oferta/${viewing.listing_id}`}>{e.chooseOther}</Link>}</div>{cancel && <Modal title={e.cancelConfirm} onClose={() => setCancel(false)}><button className="btn" onClick={() => void act("cancel")}>{e.cancelViewing}</button><button className="btn" onClick={() => setCancel(false)}>{e.cancel}</button></Modal>}</article>;
}
