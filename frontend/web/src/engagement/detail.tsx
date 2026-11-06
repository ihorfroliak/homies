"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { monthlyLabel } from "@/components/listing/format";
import type { Conversation, Listing, Viewing } from "./api";
import { Composer } from "./conversations";
import { ContactReveal } from "./contact";
import { e } from "./copy";
import { SaveButton } from "./saved";
import { useSession } from "./session";
import { ViewingPicker } from "./viewings";
import { Modal, styles, useResource } from "./ui";
import { viewingLabels, viewingTime } from "./viewing-model";
import type { Schema } from "./api";

export function DetailEngagement({ listing }: { listing: Pick<Listing, "id" | "title" | "contact_mode" | "monthly_total_estimate" | "utilities_basis" | "currency"> }) {
  const session = useSession(); const router = useRouter(); const [surface, setSurface] = useState<"message" | "viewing" | "phone" | "more">(); const [keyboard, setKeyboard] = useState(false); const [clock, setClock] = useState(() => Date.now());
  const threads = useResource<Conversation[]>(session.user ? "/v1/conversations" : null, session.user?.id);
  const viewings = useResource<Viewing[]>(session.user ? "/v1/me/viewings" : null, session.user?.id);
  const thread = threads.data?.find(item => item.listing_id === listing.id && item.my_side === "tenant" && item.status === "ACTIVE");
  const viewing = viewings.data?.find(item => item.listing_id === listing.id && ["REQUESTED", "CONFIRMED"].includes(item.status) && Date.parse(item.starts_at) > clock);
  const schedule = useResource<Schema<"ViewingSlotsOut">>(viewing ? `/v1/classifieds/${listing.id}/viewing-slots?days=1` : null);
  const restricted = session.blocked.has(listing.id);
  const [restoredSlot, setRestoredSlot] = useState<string>();
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => { const viewport = window.visualViewport; const resize = () => setKeyboard(Boolean(viewport && window.innerHeight - viewport.height > 150)); viewport?.addEventListener("resize", resize); return () => viewport?.removeEventListener("resize", resize); }, []);
  useEffect(() => {
    const intent = session.resumed;
    if (intent?.listing_id !== listing.id || !["message", "viewing", "reveal"].includes(intent.action)) return;
    session.consume(); queueMicrotask(() => { setRestoredSlot(intent.starts_at); setSurface(intent.action === "reveal" ? "phone" : intent.action === "viewing" ? "viewing" : "message"); });
  }, [session, listing.id]);
  async function open(action: "message" | "phone") { setSurface(undefined); if (await session.ensure({ action: action === "phone" ? "reveal" : "message", listing_id: listing.id })) setSurface(action); }
  const message = thread ? <Link className="btn" href={`/wiadomosci/${thread.id}`}>{e.continueThread}</Link> : <button className="btn" disabled={restricted} onClick={() => void open("message")}>{e.message}</button>;
  const booking = viewing ? <Link className="btn btn--primary" href="/ogladania">{e.seeViewing}</Link> : <button className="btn btn--primary" disabled={restricted} onClick={() => setSurface("viewing")}>{e.viewing}</button>;
  const phone = listing.contact_mode === "phone" && <button className="btn" disabled={restricted} onClick={() => void open("phone")}>{e.reveal}</button>;
  // REQUESTED and CONFIRMED read differently: only the server's state may say a viewing is arranged.
  const status = viewing && <p className={styles.viewingStatus} data-status={viewing.status}><strong>{viewingLabels[viewing.status]}</strong><span>{viewingTime(viewing.starts_at, schedule.data?.timezone)}</span></p>;
  return <>
    <section className={styles.rail} aria-labelledby="obejrzyj"><h2 id="obejrzyj">{e.railTitle}</h2>{status ?? <p className={styles.muted}>{e.railHint}</p>}{booking}{message}{phone}{restricted && <p role="status">{e.conversationUnavailable}</p>}</section>
    <section className={styles.dock} aria-label={e.listingActions} hidden={keyboard || Boolean(surface)}>{status}<strong>{monthlyLabel(listing)}</strong>{booking}<SaveButton listingId={listing.id} title={listing.title} surface="dock" /><button className="btn" onClick={() => setSurface("more")}>{e.more}</button></section>
    {surface === "more" && <Modal title={e.listingActions} onClose={() => setSurface(undefined)}><div className={styles.form}>{message}{phone}</div></Modal>}
    {surface === "message" && <Modal title={e.message} onClose={() => setSurface(undefined)}><Composer listingId={listing.id} onSent={result => { if ("conversation" in result) router.push(`/wiadomosci/${result.conversation.id}`); }} /></Modal>}
    {surface === "phone" && session.user && <Modal title={e.reveal} onClose={() => setSurface(undefined)}><ContactReveal key={`${session.user.id}:${listing.id}`} listingId={listing.id} onMessage={() => void open("message")} /></Modal>}
    {surface === "viewing" && <ViewingPicker listingId={listing.id} initialSlot={restoredSlot} onClose={() => { setSurface(undefined); setRestoredSlot(undefined); viewings.reload(); }} onMessage={() => void open("message")} />}
  </>;
}
