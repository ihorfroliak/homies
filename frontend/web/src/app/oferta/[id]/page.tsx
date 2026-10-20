import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { ApiError } from "@/api/errors";
import { errorMessage } from "@/api/messages";
import { ListingViewTracker } from "@/analytics/trackers";
import { coverOf, freshnessLabel, monthlyLabel, moveInLabel, placeLabel } from "@/components/listing/format";
import { fmt, plural, t } from "@/i18n";
import { listing as fetchListing, type Classified } from "@/search/server";
import { pageMetadata } from "@/seo";

import styles from "./detail.module.css";
import { CostBreakdown } from "@/engagement/cost-breakdown";
import { DetailEngagement } from "@/engagement/detail";

type Props = { params: Promise<{ id: string }> };

const ID = /^[A-Za-z0-9-]{1,64}$/;

/**
 * One fetch per request, shared by metadata and the page. 404 for anything not
 * public (never 410). Temporary refusals (429, 503, timeouts) become an inline
 * state with a retry, not the generic error page.
 */
const load = cache(async (id: string): Promise<Classified | ApiError> => {
  if (!ID.test(id)) notFound();
  try {
    return await fetchListing(id);
  } catch (e) {
    if (e instanceof ApiError && e.kind === "not_found") notFound();
    if (e instanceof ApiError && e.retryable) return e;
    throw e;
  }
});

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const l = await load((await params).id);
  if (l instanceof ApiError) return pageMetadata({ title: t.errors.genericTitle, page: { kind: "error" } });
  return pageMetadata({
    title: `${l.title} — ${placeLabel(l)}`,
    description: `${monthlyLabel(l)} · ${placeLabel(l)}`,
    canonicalPath: `/oferta/${l.id}`,
    page: { kind: "listing", public: true },
  });
}

export default async function ListingPage({ params }: Props) {
  const id = (await params).id;
  const l = await load(id);
  if (l instanceof ApiError) {
    return (
      <div className="container state" role="alert">
        <h1>{t.errors.genericTitle}</h1>
        <p>{errorMessage(l)}</p>
        <Link className="btn btn--primary" href={`/oferta/${id}`}>
          {t.errors.retry}
        </Link>
      </div>
    );
  }
  const freshness = freshnessLabel(l);
  const cover = coverOf(l);
  const photos = cover ? [cover, ...l.media.filter((m) => m.id !== cover.id)] : [];
  const f = l.facts;
  const backHref = l.place?.locality?.slug ? `/wynajem/${l.place.locality.slug}` : "/wynajem";

  return (
    <article className={`container ${styles.page}`}>
      <p>
        <Link href={backHref}>← {t.detail.back}</Link>
      </p>

      <header className={styles.header}>
        <h1 className={styles.title}>{l.title}</h1>
        <p className={styles.place}>{placeLabel(l)}</p>
        {freshness ? <p className={styles.fresh}>{freshness}</p> : null}
      </header>
      <div className={styles.mobileCosts}><CostBreakdown listing={l} /></div>

      {photos.length > 0 ? (
        <section aria-label={t.detail.photos} className={styles.gallery}>
          <ul>
            {photos.map((m, i) => (
              <li key={m.id}>
                {/* eslint-disable-next-line @next/next/no-img-element -- /v1/media must not go through the optimiser (FE-001 §5) */}
                <img src={m.url} alt={fmt(t.detail.photoOf, { n: i + 1, total: photos.length })} width={m.width_px ?? 800} height={m.height_px ?? 600} loading={i === 0 ? "eager" : "lazy"} decoding="async" />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className={styles.columns}>
        <div className={styles.main}>
          <section aria-labelledby="o-mieszkaniu" className={styles.section}>
            <h2 id="o-mieszkaniu">{t.detail.facts}</h2>
            <dl className={styles.facts}>
              {f?.rooms ? <Fact term={t.detail.rooms} value={plural(t.plural.rooms, f.rooms)} /> : null}
              {f?.area_m2 ? <Fact term={t.detail.area} value={`${f.area_m2} m²`} /> : null}
              {l.space_type === "ROOM" && f?.space_area_m2 ? <Fact term={t.detail.roomArea} value={`${Math.round(f.space_area_m2)} m²`} /> : null}
              {f && f.floor !== null && f.floor !== undefined ? (
                <Fact term={t.detail.floor} value={f.floor === 0 ? t.detail.ground : String(f.floor)} />
              ) : null}
              {f ? <Fact term={t.detail.elevator} value={f.has_elevator ? t.detail.yes : t.detail.no} /> : null}
              {f ? <Fact term={t.detail.furnished} value={t.filters.furnishedValues[f.furnished as "full" | "partial" | "none"] ?? f.furnished} /> : null}
              {f && f.parking !== "none" ? <Fact term={t.detail.parking} value={t.filters.parkingValues[f.parking as "street" | "spot" | "garage"] ?? f.parking} /> : null}
              {f ? <Fact term={t.detail.pets} value={f.pets_allowed ? t.detail.yes : t.detail.no} /> : null}
              <Fact term={t.detail.availability} value={moveInLabel(l)} />
              <Fact term={t.detail.term} value={l.open_ended || !l.min_term_months ? t.detail.termOpen : fmt(t.detail.termMin, { months: plural(t.plural.months, l.min_term_months) })} />
            </dl>
          </section>

          {l.description ? (
            <section aria-labelledby="opis" className={styles.section}>
              <h2 id="opis">{t.detail.description}</h2>
              <p className={styles.description}>{l.description}</p>
            </section>
          ) : null}

          <section aria-labelledby="lokalizacja" className={styles.section}>
            <h2 id="lokalizacja">{t.detail.location}</h2>
            <p>{placeLabel(l)}</p>
            <p className="small muted">{t.map.approximate}</p>
          </section>
        </div>

        <aside className={styles.aside} aria-label="Koszty i kontakt">
          <CostBreakdown listing={l} />
          <DetailEngagement listing={{ id: l.id, title: l.title, contact_mode: l.contact_mode, monthly_total_estimate: l.monthly_total_estimate, utilities_basis: l.utilities_basis, currency: l.currency }} />
        </aside>
      </div>
      <ListingViewTracker listingId={l.id} />
    </article>
  );
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value}</dd>
    </div>
  );
}
