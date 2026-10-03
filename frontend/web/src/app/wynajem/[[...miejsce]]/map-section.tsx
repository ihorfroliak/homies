import { fmt, plural, t } from "@/i18n";
import type { SearchState } from "@/search/codec";
import type { MapPage, ResolvedPlace } from "@/search/server";

import { MapLoader } from "./map-loader";
import styles from "./results.module.css";

/**
 * Map mode (DESIGN-001 §5.3). The server already fetched `/v1/classifieds/map`
 * for the same query; the client only draws it. Partial results are said in
 * words, never hidden: a capped map and the district-only listings that have
 * no public point.
 */
export function MapSection({ state, place, initial }: { state: SearchState; place: ResolvedPlace; initial?: MapPage }) {
  if (!initial) {
    return (
      <section className={styles.mapPanel} aria-label={t.map.label}>
        <div className="alert alert--warning" role="status">
          {t.map.unavailable}
        </div>
      </section>
    );
  }
  return (
    <section className={styles.mapPanel} aria-label={t.map.label}>
      {initial.truncated ? (
        <p className="alert alert--info" role="status">
          {fmt(t.map.truncated, { shown: plural(t.plural.listings, initial.points.length), total: plural(t.plural.listings, initial.total) })}
        </p>
      ) : null}
      {initial.without_point > 0 ? <p className="small muted">{fmt(t.map.withoutPoint, { count: plural(t.plural.listings, initial.without_point) })}</p> : null}
      <p className="small muted">{t.map.approximate}</p>
      <MapLoader state={state} points={initial.points} areaName={place.area?.name ?? place.locality?.name} />
    </section>
  );
}
