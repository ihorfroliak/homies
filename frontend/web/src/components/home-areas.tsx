import Link from "next/link";

import { t } from "@/i18n";
import type { GeoArea } from "@/search/server";

import styles from "./home-areas.module.css";

/** Real public area navigation. No invented map geometry, counts or prices. */
export function HomeAreas({ areas, loading = false }: { areas: Pick<GeoArea, "id" | "name" | "slug">[]; loading?: boolean }) {
  // Reference rows without a public slug cannot resolve an area page.
  const linkedAreas = areas.flatMap((area) => area.slug ? [{ ...area, slug: area.slug }] : []);
  return (
    <section className={styles.panel} aria-labelledby="home-areas-heading" aria-busy={loading}>
      <div className={styles.heading}>
        <p className={styles.eyebrow}>{t.home.areas.eyebrow}</p>
        <h2 id="home-areas-heading">{t.home.areas.heading}</h2>
        <p>{t.home.areas.body}</p>
      </div>
      {linkedAreas.length > 0 ? (
        <ul className={styles.list}>
          {linkedAreas.map((area) => (
            <li key={area.id}>
              <Link href={`/wynajem/krakow/${encodeURIComponent(area.slug)}`} prefetch={false}>
                <span>{area.name}</span><span aria-hidden="true">↗</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : <p className={styles.empty} role="status">{loading ? t.a11y.loading : t.home.areas.empty}</p>}
      <Link className={styles.all} href="/wynajem/krakow">{t.home.areas.all}<span aria-hidden="true"> →</span></Link>
    </section>
  );
}
