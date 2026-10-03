"use client";

import { useEffect, useRef, useState } from "react";

import { fmt, plural, t } from "@/i18n";
import { apiQuery, parseSearch } from "@/search/codec";

import styles from "./results.module.css";

/**
 * The filter form's submit button with a live count ("Pokaż 124 oferty"):
 * `GET /bff/v1/classifieds?…&limit=1` → `total`, debounced 300 ms, the
 * in-flight request aborted on every change. Empty fields are dropped first
 * (a GET form submits them as empty strings). A zero count warns instead of
 * disabling the button (DESIGN-001 §4).
 */
export function FilterCount({ formId, segments, localityId, areaId, initialTotal }: { formId: string; segments: string[]; localityId?: string; areaId?: string; initialTotal?: number }) {
  const [total, setTotal] = useState<number | undefined>(initialTotal);
  const [pending, setPending] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    const form = document.getElementById(formId) as HTMLFormElement | null;
    if (!form) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const recount = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        abort.current?.abort();
        const controller = new AbortController();
        abort.current = controller;
        const params = new URLSearchParams();
        for (const [k, v] of new FormData(form)) if (typeof v === "string" && v.trim() !== "") params.append(k, v);
        const { state } = parseSearch(segments, params);
        const query = new URLSearchParams();
        for (const [k, v] of Object.entries(apiQuery(state, { localityId, areaId }))) {
          for (const value of Array.isArray(v) ? v : [v]) query.append(k, String(value));
        }
        query.set("limit", "1");
        setPending(true);
        try {
          const response = await fetch(`/bff/v1/classifieds?${query}`, { signal: controller.signal, headers: { accept: "application/json" } });
          if (response.ok) setTotal(((await response.json()) as { total: number }).total);
          else setTotal(undefined);
        } catch (e) {
          if (!(e instanceof DOMException && e.name === "AbortError")) setTotal(undefined);
        } finally {
          if (abort.current === controller) setPending(false);
        }
      }, 300);
    };
    // Empty inputs must not reach the URL either.
    const onSubmit = () => {
      for (const el of Array.from(form.elements)) {
        const input = el as HTMLInputElement;
        if (input.name && "value" in input && input.value === "" && input.type !== "checkbox") input.disabled = true;
      }
    };
    form.addEventListener("input", recount);
    form.addEventListener("change", recount);
    form.addEventListener("submit", onSubmit);
    return () => {
      clearTimeout(timer);
      abort.current?.abort();
      form.removeEventListener("input", recount);
      form.removeEventListener("change", recount);
      form.removeEventListener("submit", onSubmit);
    };
  }, [formId, segments, localityId, areaId]);

  const label = total === undefined ? t.filters.apply : fmt(t.filters.showCount, { count: plural(t.plural.listings, total) });
  return (
    <span>
      <button type="submit" className="btn btn--primary" aria-busy={pending}>
        {label}
      </button>
      {total === 0 ? (
        <span role="status" className={styles.zeroWarning}>
          {t.results.emptyTitle}
        </span>
      ) : null}
    </span>
  );
}
