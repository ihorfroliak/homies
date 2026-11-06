"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import type { components } from "@/api/schema";
import { coverOf, monthlyLabel, placeLabel } from "@/components/listing/format";
import { fmt, plural, t } from "@/i18n";

import styles from "./results.module.css";

type Classified = components["schemas"]["ClassifiedOut"];
type Read = { listing: Classified } | "gone";

/** How many listings one step of the card reads; the "next" button asks for another step. */
export const CARD_STEP = 10;

/**
 * MapPoint has no title or cover (gap G5): the card reads the public detail
 * through the BFF. Every listing behind a marker stays reachable: a large stack
 * pages through its members, and a removed listing or a failed read is said, never
 * silently dropped.
 *
 * Each opened card reads afresh, because it shows prices: a remembered answer would
 * pass an old price off as current, and no freshness rule exists to bound one. What
 * is read lives only as long as the card, so paging and retry read each listing once.
 */
export function MapCard({ ids, nearby, onClose, onZoom }: { ids: string[]; nearby: boolean; onClose: () => void; onZoom?: () => void }) {
  const [limit, setLimit] = useState(CARD_STEP);
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<{ limit: number; attempt: number; items: Classified[]; gone: number; failed: number } | null>(null);
  const reads = useRef(new Map<string, Read>());
  const close = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const focusFrom = useRef<number | null>(null);
  const headingId = useId();

  useEffect(() => close.current?.focus(), []);

  useEffect(() => {
    const controller = new AbortController();
    const wanted = ids.slice(0, limit);
    void Promise.all(
      wanted.map(async (id) => {
        if (reads.current.has(id)) return;
        try {
          const response = await fetch(`/bff/v1/classifieds/${encodeURIComponent(id)}`, { signal: controller.signal, headers: { accept: "application/json" } });
          if (response.status === 404) reads.current.set(id, "gone");
          else if (response.ok) reads.current.set(id, { listing: (await response.json()) as Classified });
        } catch {
          /* Left unread: counted as failed below and offered a retry. */
        }
      }),
    ).then(() => {
      if (controller.signal.aborted) return;
      const results = wanted.map((id) => reads.current.get(id));
      setLoaded({
        limit,
        attempt,
        items: results.flatMap((r) => (r && r !== "gone" ? [r.listing] : [])),
        gone: results.filter((r) => r === "gone").length,
        failed: results.filter((r) => r === undefined).length,
      });
    });
    return () => controller.abort();
  }, [ids, limit, attempt]);

  const current = loaded?.limit === limit && loaded.attempt === attempt ? loaded : null;
  const items = current?.items ?? loaded?.items ?? [];

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
      {current && current.gone > 0 ? (
        <p role="status" className="small">
          {current.gone === 1 ? t.map.oneGone : fmt(t.map.someGone, { count: plural(t.plural.listings, current.gone) })}
        </p>
      ) : null}
      {current && current.failed > 0 ? (
        <p role="status" className="small">
          {fmt(t.map.someFailed, { count: plural(t.plural.listings, current.failed) })}{" "}
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
