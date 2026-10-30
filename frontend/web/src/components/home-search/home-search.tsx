import { fmt, t } from "@/i18n";

import styles from "./home-search.module.css";

export interface SearchArea {
  id: string;
  name: string;
  slug?: string | null;
}

const ROOM_OPTIONS = [1, 2, 3, 4] as const;

/**
 * Home search (DESIGN-001C Home Mapa, FE-VIS-001A): where (an area of the
 * launch city, or all of it), the monthly total limit and rooms. A plain GET
 * form to /szukaj, so it works without JavaScript; /szukaj turns it into the
 * canonical results URL (/wynajem/{city}[/{area}]?koszt_do=&pokoje_od=).
 */
export function HomeSearch({ cityName, areas }: { cityName: string; areas: SearchArea[] }) {
  const routable = areas.filter((a): a is SearchArea & { slug: string } => Boolean(a.slug));
  return (
    <form role="search" aria-label={t.homeSearch.label} method="get" action="/szukaj" className={styles.form}>
      <input type="hidden" name="miasto" value={cityName} />
      <div className={styles.field}>
        <label htmlFor="hs-where">{t.homeSearch.where}</label>
        <select id="hs-where" name="obszar" className={`input ${styles.select}`} defaultValue="">
          <option value="">{t.homeSearch.whereAll}</option>
          {routable.map((a) => (
            <option key={a.id} value={a.slug}>{a.name}</option>
          ))}
        </select>
      </div>
      <div className={styles.field}>
        <label htmlFor="hs-total">{t.homeSearch.maxTotal}</label>
        <input id="hs-total" name="koszt_do" className="input" type="number" inputMode="numeric" min={1} max={10000000} step={50} />
      </div>
      <fieldset className={styles.rooms}>
        <legend>{t.homeSearch.rooms}</legend>
        <div className={styles.segments}>
          <label className={styles.segment}>
            <input type="radio" name="pokoje_od" value="" defaultChecked />
            <span>{t.homeSearch.roomsAny}</span>
          </label>
          {ROOM_OPTIONS.map((n) => (
            <label key={n} className={styles.segment}>
              <input type="radio" name="pokoje_od" value={n} />
              <span>{fmt(t.homeSearch.roomsFrom, { n })}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <button type="submit" className={styles.submit}>{t.homeSearch.submit}</button>
    </form>
  );
}
