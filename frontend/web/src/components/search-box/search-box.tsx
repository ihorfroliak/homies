import { t } from "@/i18n";

import { CitySuggestions } from "./city-suggestions";
import styles from "./search-box.module.css";

/**
 * Home SearchBox (DESIGN-001 §5.1): city + max monthly cost. A plain GET form
 * to /szukaj (works without JavaScript); with JavaScript the city field gets
 * suggestions from /v1/geo/localities through the BFF.
 */
export function SearchBox() {
  return (
    <form role="search" aria-label={t.searchBox.label} method="get" action="/szukaj" className={styles.box}>
      <div className="field">
        <label htmlFor="sb-city">{t.searchBox.city}</label>
        <input id="sb-city" name="miasto" className="input" list="sb-city-list" autoComplete="off" placeholder={t.searchBox.cityPlaceholder} maxLength={80} />
        <CitySuggestions inputId="sb-city" listId="sb-city-list" />
      </div>
      <div className="field">
        <label htmlFor="sb-cost">{t.searchBox.maxCost}</label>
        <input id="sb-cost" name="koszt_do" className="input" type="number" inputMode="numeric" min={1} max={10000000} step={1} />
      </div>
      <button type="submit" className="btn btn--primary">
        {t.searchBox.submit}
      </button>
    </form>
  );
}
