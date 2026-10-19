"use client";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ApiError } from "@/api/errors";
import { api } from "./api";
import { e, errorCopy } from "./copy";
import styles from "./engagement.module.css";

export function Modal({ title, children, onClose, initialFocus }: { title: string; children: ReactNode; onClose: () => void; initialFocus?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  const id = useId();
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    const dialog = ref.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    dialog?.showModal();
    const field = initialFocus ? dialog?.querySelector<HTMLElement>(initialFocus) : undefined;
    field?.focus();
    return () => { dialog?.close(); if (opener?.isConnected) opener.focus(); else document.getElementById("engagement-status")?.focus(); };
  }, [initialFocus]);
  return <dialog ref={ref} className={styles.modal} aria-labelledby={id} onCancel={(event) => { event.preventDefault(); close.current(); }}>
    <div className={styles.modalHeader}><h2 id={id}>{title}</h2><button type="button" className="btn" onClick={onClose} aria-label={e.close}>×</button></div>{children}
  </dialog>;
}

export function useCountdown(error: unknown) {
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    const until = Date.now() + (error instanceof ApiError ? error.retryAfterSeconds ?? 0 : 0) * 1000;
    const tick = () => setRemaining(Math.max(0, Math.ceil((until - Date.now()) / 1000)));
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  }, [error]);
  return remaining;
}
export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  const remaining = useCountdown(error);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error instanceof ApiError && error.status === 409) ref.current?.focus(); }, [error]);
  useEffect(() => {
    if (!retry || !(error instanceof ApiError) || error.status !== 429) return;
    const timer = setTimeout(retry, Math.max(1, error.retryAfterSeconds ?? 1) * 1000);
    return () => clearTimeout(timer);
  }, [error, retry]);
  if (!error) return null;
  return <div ref={ref} className={styles.error} role="alert" tabIndex={-1}><p>{errorCopy(error)}</p>{remaining > 0 && <p>{e.wait} {remaining} {e.seconds}</p>}{retry && <button className="btn" disabled={remaining > 0} onClick={retry}>{e.retry}</button>}</div>;
}

/** Every request is abortable and state is scoped to its exact resource/account key. */
export function useResource<T>(path: string | null, scope = "public") {
  const key = `${scope}:${path}`;
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{ key: string; data?: T; error?: unknown }>({ key: "" });
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(path, "GET", undefined, controller.signal).then(data => { if (!controller.signal.aborted) setState({ key, data }); }, error => { if (!controller.signal.aborted) setState({ key, error }); });
    return () => controller.abort();
  }, [path, key, revision]);
  useEffect(() => {
    const focus = () => { if (document.visibilityState === "visible") reload(); };
    window.addEventListener("focus", focus); document.addEventListener("visibilitychange", focus);
    return () => { window.removeEventListener("focus", focus); document.removeEventListener("visibilitychange", focus); };
  }, [reload]);
  return { data: state.key === key ? state.data : undefined, error: state.key === key ? state.error : undefined, reload, loading: Boolean(path) && (state.key !== key || !state.data && !state.error) };
}
export function Empty({ children }: { children: ReactNode }) { return <p className={styles.empty}>{children}</p>; }
export { styles };
