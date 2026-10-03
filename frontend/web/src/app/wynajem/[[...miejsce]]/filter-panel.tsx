import Link from "next/link";

import { fmt, t } from "@/i18n";
import { activeFilters, searchHref, type SearchState } from "@/search/codec";
import type { ResolvedPlace } from "@/search/server";

import { FilterCount } from "./filter-count";
import styles from "./results.module.css";

const FURNISHED_PARAM = { full: "pelne", partial: "czesciowe", none: "brak" } as const;
const PARKING_PARAM = { street: "ulica", spot: "miejsce", garage: "garaz" } as const;

/**
 * Filters (DESIGN-001 §5.4) as a native <details> + GET form: works without
 * JavaScript and keeps the URL the single source of truth. With JavaScript the
 * submit button shows the live count. Areas are links (they change the path).
 * Order follows decision weight: place, monthly cost, move-in total, rooms,
 * size, availability, term, then the rest.
 */
export function FilterPanel({ state, place, total }: { state: SearchState; place: ResolvedPlace; total?: number }) {
  const count = activeFilters(state).length;
  const path = searchHref({ sort: "newest", page: 1, view: "list", city: state.city, area: state.area });
  return (
    <details className={styles.filters}>
      <summary className="btn btn--secondary">{count > 0 ? fmt(t.results.filtersCount, { n: count }) : t.results.filters}</summary>
      <div className={styles.filterBody}>
        {place.locality && place.areas.length > 0 ? (
          <nav aria-label={place.locality.name} className={styles.areaLinks}>
            <ul>
              {place.areas.map((a) => (
                <li key={a.id}>
                  <Link href={searchHref({ ...state, city: state.city, area: a.slug ?? undefined, page: 1, bbox: undefined })} aria-current={a.id === place.areaId ? "page" : undefined}>
                    {a.name}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
        <form method="get" action={path} id="filtry" className={styles.filterForm}>
          {state.sort !== "newest" ? <input type="hidden" name="sort" value={{ price_asc: "najtansze", price_desc: "najdrozsze", size_desc: "najwieksze", available_soonest: "najwczesniej" }[state.sort]} /> : null}
          {state.view === "map" ? <input type="hidden" name="widok" value="mapa" /> : null}
          {state.bbox ? <input type="hidden" name="mapa" value={state.bbox.join(",")} /> : null}

          <fieldset>
            <legend>{t.filters.monthly}</legend>
            <Num name="koszt_od" label={t.filters.from} value={state.monthlyMin} />
            <Num name="koszt_do" label={t.filters.to} value={state.monthlyMax} />
          </fieldset>
          <Num name="na_start_do" label={t.filters.moveIn} value={state.moveInMax} />
          <Num name="pokoje_od" label={t.filters.rooms} value={state.roomsMin} max={100} />
          <Num name="metraz_od" label={t.filters.area} value={state.areaMin} max={100000} />
          <div className="field">
            <label htmlFor="f-dostepne">{t.filters.availableBy}</label>
            <input id="f-dostepne" className="input" type="date" name="dostepne_do" defaultValue={state.availableBy} aria-describedby="f-dostepne-hint" />
            <p id="f-dostepne-hint" className="small muted">{t.filters.availableByHint}</p>
          </div>
          <Num name="okres_do" label={t.filters.termMax} value={state.termMax} max={1200} />
          <fieldset>
            <legend>{t.filters.rent}</legend>
            <Num name="najem_od" label={t.filters.from} value={state.rentMin} />
            <Num name="najem_do" label={t.filters.to} value={state.rentMax} />
          </fieldset>
          <div className="field">
            <label htmlFor="f-umebl">{t.filters.furnished}</label>
            <select id="f-umebl" name="umeblowanie" className="input" defaultValue={state.furnished ? FURNISHED_PARAM[state.furnished] : ""}>
              <option value="">{t.filters.furnishedAny}</option>
              {(Object.keys(FURNISHED_PARAM) as (keyof typeof FURNISHED_PARAM)[]).map((k) => (
                <option key={k} value={FURNISHED_PARAM[k]}>
                  {t.filters.furnishedValues[k]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-parking">{t.filters.parking}</label>
            <select id="f-parking" name="parking" className="input" defaultValue={state.parking ? PARKING_PARAM[state.parking] : ""}>
              <option value="">{t.filters.parkingAny}</option>
              {(Object.keys(PARKING_PARAM) as (keyof typeof PARKING_PARAM)[]).map((k) => (
                <option key={k} value={PARKING_PARAM[k]}>
                  {t.filters.parkingValues[k]}
                </option>
              ))}
            </select>
          </div>
          <label className={styles.check}>
            <input type="checkbox" name="zwierzeta" value="tak" defaultChecked={state.pets} /> {t.filters.pets}
          </label>
          <label className={styles.check}>
            <input type="checkbox" name="winda" value="tak" defaultChecked={state.elevator} /> {t.filters.elevator}
          </label>
          <div className={styles.filterFooter}>
            <Link href={searchHref({ sort: state.sort, page: 1, view: state.view, city: state.city, area: state.area })}>{t.results.clearAll}</Link>
            <FilterCount formId="filtry" segments={[state.city, state.area].filter((s): s is string => Boolean(s))} localityId={place.localityId} areaId={place.areaId} initialTotal={total} />
          </div>
        </form>
      </div>
    </details>
  );
}

function Num({ name, label, value, max = 10_000_000 }: { name: string; label: string; value?: number; max?: number }) {
  const id = `f-${name}`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} className="input" type="number" inputMode="numeric" min={1} max={max} step={1} name={name} defaultValue={value} />
    </div>
  );
}
