"use client";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode, type FormEvent } from "react";
import { ApiError } from "@/api/errors";
import { api } from "./api";
import { e } from "./copy";
import { readIntent, safeIntent, writeIntent, type Intent } from "./intent";
import { ErrorNotice, Modal, styles, useCountdown } from "./ui";
export interface SessionUser { id: string; name: string; phoneVerified: boolean; emailVerified: boolean }
interface Session { authenticated: boolean; user?: SessionUser }
type IntentInput = Omit<Intent, "created_at" | "initiator_id"> & { initiator_id?: string };
interface Context { user?: SessionUser; ready: boolean; ensure: (intent: IntentInput, force?: boolean) => Promise<boolean>; refresh: () => Promise<Session>; resumed?: Intent; consume: () => void; blocked: ReadonlySet<string>; block: (id: string) => void; retainDraft: () => () => void }
const SessionContext = createContext<Context | null>(null);
export function useSession() { const value = useContext(SessionContext); if (!value) throw new Error("EngagementProvider missing"); return value; }
export function EngagementProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>();
  const [intent, setIntent] = useState<Intent>();
  const [resumed, setResumed] = useState<Intent>();
  const [restrictions, setRestrictions] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState("");
  const [offline, setOffline] = useState(false);
  const resolve = useRef<((value: boolean) => void) | undefined>(undefined);
  const drafts = useRef(0);
  const retainDraft = useCallback(() => { drafts.current++; return () => { drafts.current--; }; }, []);
  const refresh = useCallback(async () => { const next = await api<Session>("/auth/session"); setSession(next); return next; }, []);
  const ensure = useCallback((input: IntentInput, force = false): Promise<boolean> => {
    if (session?.authenticated && !force) return Promise.resolve(true);
    resolve.current?.(false);
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    if (opener && !opener.id) opener.id = `intent-${crypto.randomUUID()}`;
    const pending: Intent = { ...input, initiator_id: input.initiator_id ?? opener?.id ?? "engagement-status", created_at: Date.now() };
    writeIntent(pending); setIntent(pending);
    return new Promise<boolean>(done => { resolve.current = done; });
  }, [session?.authenticated]);
  useEffect(() => {
    let active = true;
    Promise.resolve().then(refresh).then(next => {
      if (!active) return;
      const pending = readIntent();
      if (pending) { if (next.authenticated) { setResumed(pending); writeIntent(); } else setIntent(pending); }
    }).catch(() => { if (active) setSession({ authenticated: false }); });
    const on = () => setOffline(false); const off = () => setOffline(true);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { active = false; window.removeEventListener("online", on); window.removeEventListener("offline", off); resolve.current?.(false); };
  }, [refresh]);
  useEffect(() => {
    // A background session probe must not unmount an unresolved send. Explicit
    // login/logout refresh still clears identity; each resource/write is authorized by the BFF.
    const focus = () => { if (!drafts.current && document.visibilityState === "visible") void refresh().catch(() => undefined); };
    window.addEventListener("focus", focus); document.addEventListener("visibilitychange", focus);
    return () => { window.removeEventListener("focus", focus); document.removeEventListener("visibilitychange", focus); };
  }, [refresh]);
  const finish = (success: boolean) => {
    const current = safeIntent(intent);
    writeIntent(); setIntent(undefined);
    const done = resolve.current; resolve.current = undefined;
    if (success && current && !done) setResumed(current);
    setNotice(success ? e.authDone : "");
    // Continue only after the authenticated render and account-scoped effects commit.
    requestAnimationFrame(() => { (document.getElementById(current?.initiator_id ?? "") ?? document.getElementById("engagement-status"))?.focus(); done?.(success && Boolean(current)); });
  };
  const prefix = `${session?.user?.id ?? ""}:`;
  const blocked = new Set([...restrictions].filter(key => key.startsWith(prefix)).map(key => key.slice(prefix.length)));
  return <SessionContext.Provider value={{ user: session?.authenticated ? session.user : undefined, ready: Boolean(session), ensure, refresh, resumed, consume: () => setResumed(undefined), blocked, block: id => setRestrictions(prev => new Set([...prev, `${prefix}${id}`])), retainDraft }}>
    {offline && <p role="status" className={styles.error}>{e.offline}</p>}
    <p id="engagement-status" tabIndex={-1} role="status" className={notice ? styles.status : "visually-hidden"}>{notice}</p>
    {children}
    {intent && <Modal title={e.authRequired} onClose={() => finish(false)} initialFocus='input[type="email"]'><AuthForm onSuccess={() => finish(true)} /></Modal>}
  </SessionContext.Provider>;
}
export function AuthForm({ registration = false, onSuccess }: { registration?: boolean; onSuccess?: () => void }) {
  const session = useSession();
  const [register, setRegister] = useState(registration);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [exists, setExists] = useState(false);
  const wait = useCountdown(error);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (pending || wait) return;
    setPending(true); setError(undefined);
    try {
      await api(`/auth/${register ? "register" : "login"}`, "POST", { email, password, ...(register ? { full_name: name } : {}) });
      const next = await session.refresh();
      if (!next.authenticated) throw new ApiError({ kind: "unauthorized", status: 401 });
      setPassword(""); onSuccess?.();
    } catch (error) { if (error instanceof ApiError && error.status === 409 && register) { setRegister(false); setExists(true); } else setError(error); }
    finally { setPending(false); }
  }
  if (session.user && !onSuccess) return <p role="status">{e.authDone} <Link href="/zapisane">{e.saved}</Link></p>;
  return <form onSubmit={submit} className={styles.form} aria-busy={pending}>
    <div className={styles.actions}><button type="button" className="btn" aria-pressed={!register} onClick={() => setRegister(false)}>{e.login}</button><button type="button" className="btn" aria-pressed={register} onClick={() => setRegister(true)}>{e.register}</button></div>
    {exists && <p role="status">{e.registerConflict}</p>}
    <label>{e.email}<input type="email" name="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
    <label>{e.password}<input type="password" name="password" autoComplete={register ? "new-password" : "current-password"} minLength={register ? 10 : undefined} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
    {register && <label>{e.name}<input autoComplete="name" value={name} onChange={event => setName(event.target.value)} maxLength={200} /></label>}
    {error instanceof ApiError && error.status === 401 ? <p role="alert">{e.authFailed}</p> : <ErrorNotice error={error} />}
    <button className="btn btn--primary" disabled={pending || wait > 0}>{pending ? e.loading : register ? e.register : e.login}</button>
  </form>;
}
export function RequireSession({ children }: { children: ReactNode }) {
  const { user, ready, ensure } = useSession();
  if (!ready) return <p aria-busy="true">{e.loading}</p>;
  return user ? children : <div><p>{e.authRequired}</p><button className="btn btn--primary" onClick={() => void ensure({ action: "account" })}>{e.login}</button></div>;
}
