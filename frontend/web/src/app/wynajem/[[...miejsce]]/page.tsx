import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { errorMessage } from "@/api/messages";
import type { ApiError } from "@/api/errors";
import { SearchTracker } from "@/analytics/trackers";
import { ListingCard } from "@/components/listing/listing-card";
import { fmt, plural, t } from "@/i18n";
import { activeFilters, apiQuery, isBare, MAX_PAGE, PAGE_SIZE, parseSearch, searchHref, type SearchState } from "@/search/codec";
import { mapPage, relaxations, resolvePlace, searchKey, searchOnce, type MapPage, type ResolvedPlace } from "@/search/server";
import { pageMetadata } from "@/seo";

import { Chips } from "./chips";
import { FilterPanel } from "./filter-panel";
import { MapSection } from "./map-section";
import styles from "./results.module.css";
import { SortForm } from "./sort-form";
import { chipLabel } from "./labels";

type Props = { params: Promise<{ miejsce?: string[] }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

function toParams(raw: Record<string, string | string[] | undefined>): URLSearchParams {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(raw)) for (const value of Array.isArray(v) ? v : v === undefined ? [] : [v]) p.append(k, value);
  return p;
}

async function load(props: Props) {
  const segments = (await props.params).miejsce ?? [];
  const parsed = parseSearch(segments, toParams(await props.searchParams));
  if (parsed.badPath) notFound();
  const place = await resolvePlace(parsed.state.city, parsed.state.area);
  if (place === null) notFound();
  return { ...parsed, place };
}

function heading(place: ResolvedPlace): string {
  if (place.locality && place.area) return fmt(t.results.headingArea, { area: place.area.name, city: place.locality.name });
  if (place.locality) return fmt(t.results.headingCity, { city: place.locality.name });
  return t.results.headingCountry;
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const { state, place } = await load(props);
  const ids = { localityId: place.localityId, areaId: place.areaId };
  const { page } = await searchOnce(searchKey(state, ids));
  const bare: SearchState = { sort: "newest", page: 1, view: "list", city: state.city, area: state.area };
  return pageMetadata({
    title: heading(place),
    canonicalPath: searchHref(bare),
    page: { kind: "results", filtered: !isBare(state), page: state.page, total: page?.total ?? 0, mapView: state.view === "map" },
  });
}

export default async function ResultsPage(props: Props) {
  const loaded = await load(props);
  const { place } = loaded;
  const ids = { localityId: place.localityId, areaId: place.areaId };
  const search = await searchOnce(searchKey(loaded.state, ids));
  const { state, page } = search;
  const error: ApiError | undefined = search.error;
  const dropped = [...loaded.dropped, ...search.refused];
  let map: MapPage | undefined;
  if (state.view === "map" && page) map = await mapPage(state, ids).catch(() => undefined);
  const relax = page && page.total === 0 ? await relaxations(state, ids).catch(() => []) : [];
  const filters = activeFilters(state);
  const searchId = crypto.randomUUID();
  const lastPage = page ? Math.min(MAX_PAGE, Math.max(1, Math.ceil(page.total / PAGE_SIZE))) : 1;
  const api = apiQuery(state, ids);
  const dimensions = Object.keys(api).filter((k) => k !== "country_code" && k !== "sort");
  const band = state.monthlyMax ?? state.monthlyMin;

  return (
    <div className={`container ${styles.page}`}>
      <header className={styles.header}>
        <h1 className={styles.title}>{heading(place)}</h1>
        <p className={styles.count} aria-live="polite">
          {page ? plural(t.plural.listingsFound, page.total) : error ? "" : t.results.searching}
        </p>
        {!place.locality ? <p className="muted">{t.results.preSearch}</p> : null}
      </header>

      {dropped.length > 0 ? (
        <div className="alert alert--info" role="status">
          {t.results.droppedParams}
        </div>
      ) : null}

      <div className={styles.toolbar}>
        <FilterPanel state={state} place={place} total={page?.total} />
        <SortForm state={state} />
        <nav aria-label={t.results.viewSwitch} className={styles.views}>
          <Link href={searchHref({ ...state, view: "list", page: 1 })} aria-current={state.view === "list" ? "page" : undefined} className={styles.view}>
            {t.results.list}
          </Link>
          <Link href={searchHref({ ...state, view: "map", page: 1 })} aria-current={state.view === "map" ? "page" : undefined} className={styles.view}>
            {t.results.map}
          </Link>
        </nav>
      </div>

      {filters.length > 0 ? <Chips state={state} labels={Object.fromEntries(filters.map((f) => [f, chipLabel(f, state)]))} /> : null}

      {error ? (
        <div className="alert alert--danger" role="alert">
          <p>{errorMessage(error)}</p>
          <Link className="btn btn--secondary" href={searchHref(state)}>
            {t.errors.retry}
          </Link>
        </div>
      ) : null}

      <div className={state.view === "map" ? styles.split : undefined}>
        {page ? (
          <section id="wyniki" aria-label={t.results.resultsRegion} className={styles.results}>
            {page.total === 0 ? (
              <div className="state">
                <h2>{t.results.emptyTitle}</h2>
                <p>{t.results.emptyBody}</p>
                {relax.length > 0 ? (
                  <ul className={styles.relax}>
                    {relax.map((r) => (
                      <li key={r.remove}>
                        <Link href={searchHref({ ...state, [r.remove]: undefined, page: 1 })}>
                          {fmt(t.results.relax, { label: chipLabel(r.remove, state), count: plural(t.plural.listings, r.total) })}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <ol className={styles.grid}>
                {page.items.map((item, i) => (
                  <li key={item.id}>
                    <ListingCard listing={item} position={(state.page - 1) * PAGE_SIZE + i + 1} priority={i < 2} />
                  </li>
                ))}
              </ol>
            )}
            {page.total > 0 ? <Pagination state={state} lastPage={lastPage} total={page.total} /> : null}
          </section>
        ) : null}
        {state.view === "map" ? <MapSection state={state} place={place} initial={map} /> : null}
      </div>

      {page ? (
        <SearchTracker
          searchId={searchId}
          route={place.area ? "/wynajem/[miasto]/[obszar]" : place.locality ? "/wynajem/[miasto]" : "/wynajem"}
          dimensions={dimensions}
          localityId={place.localityId}
          areaId={place.areaId}
          sort={state.sort}
          resultCount={page.total}
          pageIndex={state.page}
          visibleCount={page.items.length}
          priceBand={band !== undefined ? Math.floor(band / 500) * 500 : undefined}
          surface={state.view}
          containerId="wyniki"
        />
      ) : null}
    </div>
  );
}

function Pagination({ state, lastPage, total }: { state: SearchState; lastPage: number; total: number }) {
  const hasMore = state.page < lastPage;
  const capped = total > MAX_PAGE * PAGE_SIZE && state.page >= MAX_PAGE;
  const pages = Array.from({ length: lastPage }, (_, i) => i + 1).filter((n) => n === 1 || n === lastPage || Math.abs(n - state.page) <= 2);
  return (
    <div className={styles.pagination}>
      {hasMore ? (
        <Link className="btn btn--secondary" href={searchHref({ ...state, page: state.page + 1 })}>
          {t.results.showMore}
        </Link>
      ) : null}
      {capped ? <p className="muted">{t.results.narrow}</p> : null}
      {lastPage > 1 ? (
        <nav aria-label={t.results.pagination}>
          <ul className={styles.pages}>
            {pages.map((n) => (
              <li key={n}>
                <Link href={searchHref({ ...state, page: n })} aria-current={n === state.page ? "page" : undefined} aria-label={fmt(t.results.page, { n })}>
                  {n}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </div>
  );
}
