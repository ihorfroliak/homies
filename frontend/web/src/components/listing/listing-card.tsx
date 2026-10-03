import Link from "next/link";

import type { components } from "@/api/schema";
import { fmt, formatMoney, t } from "@/i18n";

import { coverOf, factsLine, freshnessLabel, monthlyLabel, moveInLabel, placeLabel } from "./format";
import styles from "./listing-card.module.css";

type Classified = components["schemas"]["ClassifiedOut"];

/**
 * ListingCard (DESIGN-001 §5.2). The whole card is one link (the title), so
 * keyboard and screen-reader users get one stop per listing. Photos are plain
 * lazy <img> with explicit size (no image optimiser on /v1/media, FE-001 §5).
 * The save button arrives with FE-003.
 */
export function ListingCard({ listing, position, priority = false }: { listing: Classified; position?: number; priority?: boolean }) {
  const cover = coverOf(listing);
  const facts = factsLine(listing);
  const freshness = freshnessLabel(listing);
  const href = `/oferta/${listing.id}`;
  return (
    <article className={styles.card}>
      <div className={styles.media}>
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- /v1/media must not go through the optimiser (FE-001 §5)
          <img src={cover.url} alt="" width={cover.width_px ?? 400} height={cover.height_px ?? 300} loading={priority ? "eager" : "lazy"} decoding="async" />
        ) : (
          <span className={styles.noPhoto}>{t.card.noPhoto}</span>
        )}
      </div>
      <div className={styles.body}>
        <p className={styles.price}>{monthlyLabel(listing)}</p>
        <p className={styles.secondary}>{fmt(t.card.rentAndMoveIn, { rent: formatMoney(listing.rent_amount), moveIn: formatMoney(listing.move_in_total) })}</p>
        <h3 className={styles.title}>
          <Link href={href} className={styles.link} data-listing-id={listing.id} data-position={position}>
            {listing.title}
          </Link>
        </h3>
        <p className={styles.meta}>{placeLabel(listing)}</p>
        {facts.length > 0 ? <p className={styles.meta}>{facts.join(" · ")}</p> : null}
        <p className={styles.meta}>{moveInLabel(listing)}</p>
        {freshness ? <p className={styles.fresh}>{freshness}</p> : null}
      </div>
    </article>
  );
}
