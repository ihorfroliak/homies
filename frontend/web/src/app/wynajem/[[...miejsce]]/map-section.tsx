import Link from "next/link";

import { fmt, plural, t } from "@/i18n";
import { searchHref, type SearchState } from "@/search/codec";
import type { MapPage, ResolvedPlace } from "@/search/server";

import { MapLoader } from "./map-loader";
import styles from "./results.module.css";

/**
 * Map mode (DESIGN-001 §5.3). The server already fetched `/v1/classifieds/map`
 * for the same query; the client only draws it. Partial results are said in
 * words, never hidden: a capped map and the district-only listings that have
 * no public point. Below 1024 px the list is not on screen, so both notes that
 * send the reader there carry a link.
 */
export function MapSection({ state, place, initial }: { state: SearchState; place: ResolvedPlace; initial?: MapPage }) {
  const list = searchHref({ ...state, view: "list", page: 1 });
  if (!initial) {
    return (
      <section className={styles.mapPanel} aria-label={t.map.label}>
        <div className="alert alert--warning" role="status">
          <p>{t.map.unavailable}</p>
          <Link href={list}>{t.map.switchToList}</Link>
        </div>
      </section>
    );
  }
  return (
    <section id="mapa" tabIndex={-1} className={styles.mapPanel} aria-label={t.map.label}>
      {initial.truncated ? (
        <p className="alert alert--info" role="status">
          {fmt(t.map.truncated, { shown: plural(t.plural.listings, initial.points.length), total: plural(t.plural.listings, initial.total) })}
        </p>
      ) : null}
      <MapLoader key={searchHref(state)} state={state} points={initial.points} areaName={place.area?.name ?? place.locality?.name} />
      <p className={styles.mapNote}>
        {t.map.approximate}
        {initial.without_point > 0 ? (
          <>
            {" "}
            <Link href={list}>{fmt(t.map.withoutPoint, { count: plural(t.plural.listings, initial.without_point) })}</Link>
          </>
        ) : null}
      </p>
    </section>
  );
}
