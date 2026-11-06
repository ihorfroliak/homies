"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import type { components } from "@/api/schema";
import { coverOf, monthlyLabel, placeLabel } from "@/components/listing/format";
import { fmt, plural, t } from "@/i18n";

import styles from "./results.module.css";

type Classified = components["schemas"]["ClassifiedOut"];

/** How many listings one step of the card reads; the "next" button asks for another step. */
export const CARD_STEP = 10;
/** Details already read in this page view (bounded), so reopening a stack costs nothing. */
const details = new Map<string, Classified>();
function remember(l: Classified) {
  details.set(l.id, l);
  if (details.size > 200) details.delete(details.keys().next().value as string);
}

/**
 * MapPoint has no title or cover (gap G5): the card reads the public detail
 * through the BFF. Every listing behind a marker stays reachable: a large stack
 * pages through its members and a failed read is said, never silently dropped.
 */
export function MapCard({ ids, nearby, onClose, onZoom }: { ids: string[]; nearby: boolean; onClose: () => void; onZoom?: () => void }) {
  const [limit, setLimit] = useState(CARD_STEP);
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<{ limit: number; attempt: number; items: Classified[] } | null>(null);
  const close = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const focusFrom = useRef<number | null>(null);
  const headingId = useId();

  useEffect(() => close.current?.focus(), []);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all(
      ids.slice(0, limit).map(async (id) => {
        const known = details.get(id);
        if (known) return known;
        try {
          const response = await fetch(`/bff/v1/classifieds/${encodeURIComponent(id)}`, { signal: controller.signal, headers: { accept: "application/json" } });
          if (!response.ok) return null;
          const listing = (await response.json()) as Classified;
          remember(listing);
          return listing;
        } catch {
          return null;
        }
      }),
    ).then((rows) => {
      if (!controller.signal.aborted) setLoaded({ limit, attempt, items: rows.filter((r): r is Classified => r !== null) });
    });
    return () => controller.abort();
  }, [ids, limit, attempt]);

  const current = loaded?.limit === limit && loaded.attempt === attempt ? loaded : null;
  const items = current?.items ?? loaded?.items ?? [];
  const missing = current ? Math.min(limit, ids.length) - current.items.length : 0;

  // After the "next" button the control may disappear: focus moves to the first new listing.
  useEffect(() => {
    if (!current || focusFrom.current === null) return;
    list.current?.querySelectorAll("a")[focusFrom.current]?.focus();
    focusFrom.current = null;
  }, [current]);

  const count = plural(t.plural.listings, ids.length);
  return (
    <div className={styles.mapCard} role="dialog" aria-modal="false" aria-labelledby={headingId} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <div className={styles.mapCardHead}>
        <h2 id={headingId} className={styles.mapCardTitle}>{ids.length > 1 ? fmt(nearby ? t.map.nearby : t.map.stack, { count }) : count}</h2>
        <button ref={close} type="button" className={`btn btn--ghost ${styles.mapCardClose}`} onClick={onClose} aria-label={t.map.close}>
          ×
        </button>
      </div>
      {!current ? <p role="status" className="small muted">{t.a11y.loading}</p> : null}
      <ul ref={list} className={styles.mapCardList}>
        {items.map((l) => {
          const cover = coverOf(l);
          return (
            <li key={l.id}>
              {cover ? (
                // eslint-disable-next-line @next/next/no-img-element -- /v1/media must not go through the optimiser (FE-001 §5)
                <img src={cover.url} alt="" width={96} height={72} loading="lazy" />
              ) : null}
              <div>
                <p className={styles.mapCardPrice}>{monthlyLabel(l)}</p>
                <Link href={`/oferta/${l.id}`}>{l.title}</Link>
                <p className="small muted">{placeLabel(l)}</p>
              </div>
            </li>
          );
        })}
      </ul>
      {missing > 0 ? (
        <p role="status" className="small">
          {fmt(t.map.someFailed, { count: plural(t.plural.listings, missing) })}{" "}
          <button type="button" className={styles.textButton} onClick={() => setAttempt((a) => a + 1)}>
            {t.errors.retry}
          </button>
        </p>
      ) : null}
      {ids.length > limit || onZoom ? (
        <div className={styles.mapCardActions}>
          {ids.length > limit ? (
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => {
                focusFrom.current = items.length;
                setLimit((n) => n + CARD_STEP);
              }}
            >
              {fmt(t.map.showNext, { shown: limit, total: ids.length })}
            </button>
          ) : null}
          {onZoom ? (
            <button type="button" className="btn btn--secondary" onClick={onZoom}>
              {t.map.zoomHere}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
