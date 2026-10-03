import Link from "next/link";

import { fmt, t } from "@/i18n";
import { activeFilters, changed, searchHref, type FilterKey, type SearchState } from "@/search/codec";

import styles from "./results.module.css";

/** Removable filter chips: each is a link to the same search without that filter. */
export function Chips({ state, labels }: { state: SearchState; labels: Partial<Record<FilterKey, string>> }) {
  const filters = activeFilters(state);
  return (
    <div className={styles.chips}>
      <ul className={styles.chipList}>
        {filters.map((key) => (
          <li key={key}>
            <Link className={styles.chip} href={searchHref(changed(state, { [key]: undefined }))} aria-label={fmt(t.results.removeChip, { label: labels[key] ?? key })}>
              {labels[key]} <span aria-hidden="true">×</span>
            </Link>
          </li>
        ))}
      </ul>
      {state.bbox ? <p className="small muted">{t.filters.mapAreaHint}</p> : null}
      <Link className="small" href={searchHref({ sort: state.sort, page: 1, view: state.view, city: state.city, area: state.area })}>
        {t.results.clearAll}
      </Link>
    </div>
  );
}
