import Link from "next/link";

import { fmt, t } from "@/i18n";
import { activeFilters, changed, searchHref, type FilterKey, type SearchState } from "@/search/codec";

import { LinkPending } from "./link-pending";
import styles from "./results.module.css";

/**
 * Removable chips: each is a link to the same search without that constraint.
 * The chosen neighbourhood is a constraint too, shown first; removing it returns
 * to the whole city and keeps the filters. "Wyczyść filtry" keeps the place.
 */
export function Chips({ state, labels, areaName }: { state: SearchState; labels: Partial<Record<FilterKey, string>>; areaName?: string }) {
  const filters = activeFilters(state);
  return (
    <div className={styles.chips}>
      <ul className={styles.chipList}>
        {areaName ? (
          <li>
            <Link className={`${styles.chip} ${styles.chipPlace}`} href={searchHref(changed(state, { area: undefined, bbox: undefined }))} aria-label={fmt(t.results.removeArea, { area: areaName })}>
              {areaName} <span aria-hidden="true">×</span>
              <LinkPending />
            </Link>
          </li>
        ) : null}
        {filters.map((key) => (
          <li key={key}>
            <Link className={styles.chip} href={searchHref(changed(state, { [key]: undefined }))} aria-label={fmt(t.results.removeChip, { label: labels[key] ?? key })}>
              {labels[key]} <span aria-hidden="true">×</span>
              <LinkPending />
            </Link>
          </li>
        ))}
      </ul>
      {state.bbox ? <p className="small muted">{t.filters.mapAreaHint}</p> : null}
      {filters.length > 0 ? (
        <Link className="small" href={searchHref({ sort: state.sort, page: 1, view: state.view, city: state.city, area: state.area })}>
          {t.results.clearAll}
          <LinkPending />
        </Link>
      ) : null}
    </div>
  );
}
