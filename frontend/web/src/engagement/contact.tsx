"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { usePathname } from "next/navigation";
import { ApiError } from "@/api/errors";
import { api, uncertain, type Schema } from "./api";
import { trackEngagement } from "./analytics";
import { e } from "./copy";
import { useSession } from "./session";
import { ErrorNotice, styles, useCountdown, useResource } from "./ui";

/** The disclosed number lives only in this mounted reveal surface. */
export function ContactReveal({ listingId, onMessage }: { listingId: string; onMessage: () => void }) {
  const session = useSession(); const pathname = usePathname();
  const [phone, setPhone] = useState<{ value: string; owner: string; path: string }>();
  const [error, setError] = useState<unknown>(); const [pending, setPending] = useState(false);
  const [verify, setVerify] = useState(!session.user?.phoneVerified);
  const quota = useResource<Schema<"RevealQuotaOut">>(session.user ? "/v1/me/reveal-quota" : null, session.user?.id);
  const wait = useCountdown(error); const restricted = session.blocked.has(listingId);
  const disclosure = useRef(0);
  useEffect(() => {
    const invalidate = () => { disclosure.current++; };
    const clear = () => { invalidate(); setPhone(undefined); };
    window.addEventListener("blur", clear); document.addEventListener("visibilitychange", clear);
    return () => { invalidate(); window.removeEventListener("blur", clear); document.removeEventListener("visibilitychange", clear); };
  }, []);
  async function reveal() {
    setPhone(undefined); setError(undefined);
    if (!await session.ensure({ action: "reveal", listing_id: listingId })) return;
    if (!session.user?.phoneVerified) { setVerify(true); return; }
    setPending(true);
    const epoch = ++disclosure.current;
    const quota_bucket = quota.data ? quota.data.remaining === 0 ? "empty" : quota.data.remaining < 5 ? "low" : "available" : "unknown";
    try { const value = await api<Schema<"ContactRevealOut">>(`/v1/classifieds/${listingId}/contact`, "POST"); if (epoch === disclosure.current && document.visibilityState === "visible") setPhone({ value: value.contact_phone, owner: session.user.id, path: pathname }); quota.reload(); trackEngagement("contact_reveal_submitted", { listing_id: listingId, outcome: "success", quota_bucket }); }
    catch (error) { setError(error); trackEngagement("contact_reveal_submitted", { listing_id: listingId, outcome: uncertain(error) ? "unknown" : "refused", quota_bucket }); if (error instanceof ApiError) { if (error.code === "RECONTACT_BLOCKED") { session.block(listingId); trackEngagement("engagement_refused", { surface: "reveal", code: error.code }); } if (error.code === "PHONE_NOT_VERIFIED") setVerify(true); if (error.status === 401) await session.ensure({ action: "reveal", listing_id: listingId }, true); } }
    finally { setPending(false); }
  }
  if (restricted) return <p role="status">{e.phoneUnavailable}</p>;
  if (verify) return <PhoneVerification onDone={() => { setVerify(false); setError(undefined); }} />;
  return <div className={styles.form}><p>{quota.data ? `${e.quota}: ${quota.data.remaining} z ${quota.data.limit}` : e.loading}</p><ErrorNotice error={quota.error} retry={quota.reload} /><button className="btn btn--primary" onClick={() => void reveal()} disabled={pending || wait > 0} aria-busy={pending}>{e.reveal}</button><ErrorNotice error={error} />{error instanceof ApiError && error.code === "MESSAGES_ONLY" && <button className="btn" onClick={onMessage}>{e.message}</button>}{phone?.owner === session.user?.id && phone?.path === pathname && !error && <p data-contact-reveal><a href={`tel:${phone.value}`}>{phone.value}</a></p>}</div>;
}
function PhoneVerification({ onDone }: { onDone: () => void }) {
  const session = useSession(); const [phone, setPhone] = useState(""); const [code, setCode] = useState(""); const [started, setStarted] = useState(false); const [done, setDone] = useState(false); const [error, setError] = useState<unknown>(); const [pending, setPending] = useState(false); const wait = useCountdown(error);
  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(undefined);
    try {
      if (!started) { await api("/v1/me/verify/phone/start", "POST", { phone }); setStarted(true); }
      else { await api("/v1/me/verify/phone/confirm", "POST", { code }); await session.refresh(); setCode(""); setPhone(""); setDone(true); }
    } catch (error) { setError(error); if (error instanceof ApiError && error.status === 401) await session.ensure({ action: "reveal" }, true); } finally { setPending(false); }
  }
  if (done) return <div><p role="status">{e.verifiedPhone}</p><button className="btn" onClick={onDone}>{e.back}</button></div>;
  return <form className={styles.form} onSubmit={submit}><h3>{e.verifyPhone}</h3>{!started ? <label>{e.phone}<input type="tel" autoComplete="tel" pattern="\+[1-9][0-9]{7,14}" required value={phone} onChange={event => setPhone(event.target.value)} /></label> : <label>{e.code}<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{4,8}" required value={code} onChange={event => setCode(event.target.value)} /></label>}<ErrorNotice error={error} /><button className="btn btn--primary" disabled={pending || wait > 0}>{started ? e.confirmCode : e.sendCode}</button>{started && <button type="button" className="btn" onClick={() => setStarted(false)}>{e.sendCode}</button>}</form>;
}
