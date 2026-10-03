import { t } from "@/i18n";
import { searchHref, type SearchState, type Sort } from "@/search/codec";

import { AutoSubmit } from "./auto-submit";
import styles from "./results.module.css";

const SORT_PARAM: Record<Sort, string> = { newest: "najnowsze", price_asc: "najtansze", price_desc: "najdrozsze", size_desc: "najwieksze", available_soonest: "najwczesniej" };

/**
 * Sort as a plain GET form (works without JavaScript); with JavaScript the
 * select submits itself on change. The current filters ride along as hidden
 * fields taken from the canonical URL, and the page resets to 1.
 */
export function SortForm({ state }: { state: SearchState }) {
  const href = searchHref({ ...state, sort: "newest", page: 1 });
  const [path, query = ""] = href.split("?");
  const hidden = [...new URLSearchParams(query)];
  return (
    <form method="get" action={path} className={styles.sort}>
      {hidden.map(([k, v]) => (
        <input key={k} type="hidden" name={k} value={v} />
      ))}
      <label htmlFor="sort">{t.results.sort}</label>
      <select id="sort" name="sort" defaultValue={SORT_PARAM[state.sort]} className="input">
        {(Object.keys(SORT_PARAM) as Sort[]).map((s) => (
          <option key={s} value={SORT_PARAM[s]}>
            {t.results.sorts[s]}
          </option>
        ))}
      </select>
      <AutoSubmit selectId="sort" />
      <noscript>
        <button type="submit" className="btn btn--secondary">
          {t.results.sort}
        </button>
      </noscript>
    </form>
  );
}
