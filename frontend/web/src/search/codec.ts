/**
 * The one Polish URL codec for search (DESIGN-001 §8).
 *
 *   /wynajem[/{miasto}[/{obszar}]]?koszt_do=4000&pokoje_od=2&sort=najtansze&strona=2&widok=mapa
 *
 * Parsing never throws: unknown or invalid parameters are dropped and named in
 * `dropped`, so the page can say "Pominęliśmy nieprawidłowy filtr" and still
 * search. Serialising is canonical: fixed order, defaults omitted, so one
 * search has one URL (and one `search_id` dimension set). Money in the URL is
 * whole złoty; the API takes integer minor units (×100).
 */
export type Sort = "newest" | "price_asc" | "price_desc" | "size_desc" | "available_soonest";
export type Furnished = "full" | "partial" | "none";
export type Parking = "street" | "spot" | "garage";
export type View = "list" | "map";

export interface SearchState {
  city?: string;
  area?: string;
  monthlyMin?: number;
  monthlyMax?: number;
  rentMin?: number;
  rentMax?: number;
  moveInMax?: number;
  roomsMin?: number;
  areaMin?: number;
  furnished?: Furnished;
  parking?: Parking;
  pets?: true;
  elevator?: true;
  availableBy?: string;
  termMax?: number;
  sort: Sort;
  page: number;
  view: View;
  bbox?: [number, number, number, number];
}

export const PAGE_SIZE = 24;
export const MAX_OFFSET = 10_000;
export const MAX_PAGE = Math.floor(MAX_OFFSET / PAGE_SIZE) + 1;

const SORTS: Record<string, Sort> = {
  najnowsze: "newest",
  najtansze: "price_asc",
  najdrozsze: "price_desc",
  najwieksze: "size_desc",
  najwczesniej: "available_soonest",
};
const SORT_SLUG = Object.fromEntries(Object.entries(SORTS).map(([k, v]) => [v, k])) as Record<Sort, string>;
const FURNISHED: Record<string, Furnished> = { pelne: "full", czesciowe: "partial", brak: "none" };
const FURNISHED_SLUG = Object.fromEntries(Object.entries(FURNISHED).map(([k, v]) => [v, k])) as Record<Furnished, string>;
const PARKING: Record<string, Parking> = { ulica: "street", miejsce: "spot", garaz: "garage" };
const PARKING_SLUG = Object.fromEntries(Object.entries(PARKING).map(([k, v]) => [v, k])) as Record<Parking, string>;

// Same shape and limit as the backend (GET /v1/geo/localities/by-slug: 120).
const SLUG = /^(?=.{1,120}$)[a-z0-9]+(-[a-z0-9]+)*$/;
const DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Whole złoty, 1 … 10 000 000 (the backend caps money far above any rent). */
const MAX_ZLOTY = 10_000_000;

interface IntRule {
  min: number;
  max: number;
}

function int(raw: string, rule: IntRule): number | undefined {
  if (!/^\d{1,9}$/.test(raw)) return undefined;
  const n = Number(raw);
  return n >= rule.min && n <= rule.max ? n : undefined;
}

function validDate(raw: string): string | undefined {
  const m = DATE.exec(raw);
  if (!m) return undefined;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return d.getUTCFullYear() === Number(m[1]) && d.getUTCMonth() === Number(m[2]) - 1 && d.getUTCDate() === Number(m[3]) ? raw : undefined;
}

function bboxOf(raw: string): [number, number, number, number] | undefined {
  const parts = raw.split(",");
  if (parts.length !== 4 || parts.some((p) => !/^-?\d{1,3}(\.\d{1,6})?$/.test(p))) return undefined;
  const [w, s, e, n] = parts.map(Number) as [number, number, number, number];
  if (w < -180 || e > 180 || s < -90 || n > 90 || w >= e || s >= n) return undefined;
  return [w, s, e, n];
}

export interface Parsed {
  state: SearchState;
  /** Query parameter names that were present but unusable. */
  dropped: string[];
  /** The path had more than city/area, or a malformed slug: the caller answers 404. */
  badPath: boolean;
}

export function parseSearch(segments: readonly string[], params: URLSearchParams): Parsed {
  const state: SearchState = { sort: "newest", page: 1, view: "list" };
  const dropped: string[] = [];
  let badPath = segments.length > 2;
  // A malformed escape ("/wynajem/%C0") is a bad path (404), never an exception.
  const decoded = segments.map((s) => {
    try {
      return decodeURIComponent(s).toLowerCase();
    } catch {
      badPath = true;
      return "";
    }
  });
  const [city, area] = decoded;
  if (city !== undefined) {
    if (SLUG.test(city)) state.city = city;
    else badPath = true;
  }
  if (area !== undefined) {
    if (SLUG.test(area)) state.area = area;
    else badPath = true;
  }

  const seen = new Set<string>();
  for (const [key, raw] of params) {
    if (seen.has(key)) {
      dropped.push(key); // repeated single-value parameter: the first one wins
      continue;
    }
    seen.add(key);
    const value = raw.trim();
    const take = <T>(parsed: T | undefined, apply: (v: T) => void) => {
      if (parsed === undefined) dropped.push(key);
      else apply(parsed);
    };
    const money = { min: 1, max: MAX_ZLOTY };
    switch (key) {
      case "koszt_od": take(int(value, money), (v) => (state.monthlyMin = v)); break;
      case "koszt_do": take(int(value, money), (v) => (state.monthlyMax = v)); break;
      case "najem_od": take(int(value, money), (v) => (state.rentMin = v)); break;
      case "najem_do": take(int(value, money), (v) => (state.rentMax = v)); break;
      case "na_start_do": take(int(value, money), (v) => (state.moveInMax = v)); break;
      case "pokoje_od": take(int(value, { min: 1, max: 100 }), (v) => (state.roomsMin = v)); break;
      case "metraz_od": take(int(value, { min: 1, max: 100_000 }), (v) => (state.areaMin = v)); break;
      case "okres_do": take(int(value, { min: 1, max: 1200 }), (v) => (state.termMax = v)); break;
      case "umeblowanie": take(FURNISHED[value], (v) => (state.furnished = v)); break;
      case "parking": take(PARKING[value], (v) => (state.parking = v)); break;
      case "zwierzeta": take(value === "tak" ? (true as const) : undefined, (v) => (state.pets = v)); break;
      case "winda": take(value === "tak" ? (true as const) : undefined, (v) => (state.elevator = v)); break;
      case "dostepne_do": take(validDate(value), (v) => (state.availableBy = v)); break;
      case "sort": take(SORTS[value], (v) => (state.sort = v)); break;
      case "strona": take(int(value, { min: 1, max: MAX_PAGE }), (v) => (state.page = v)); break;
      case "widok": take(value === "mapa" ? ("map" as const) : value === "lista" ? ("list" as const) : undefined, (v) => (state.view = v)); break;
      case "mapa": take(bboxOf(value), (v) => (state.bbox = v)); break;
      default:
        // Attribution parameters are not search filters; anything else is unknown.
        if (!key.startsWith("utm_")) dropped.push(key);
    }
  }
  // Inverted ranges are a user typo, not a search: drop both ends of the pair.
  const pairs: [keyof SearchState, keyof SearchState, string, string][] = [
    ["monthlyMin", "monthlyMax", "koszt_od", "koszt_do"],
    ["rentMin", "rentMax", "najem_od", "najem_do"],
  ];
  for (const [lo, hi, a, b] of pairs) {
    const low = state[lo] as number | undefined;
    const high = state[hi] as number | undefined;
    if (low !== undefined && high !== undefined && low > high) {
      delete state[lo];
      delete state[hi];
      dropped.push(a, b);
    }
  }
  return { state, dropped, badPath };
}

/** Canonical URL (path + query) of a search state. */
export function searchHref(state: SearchState): string {
  const path = ["/wynajem", state.city, state.city ? state.area : undefined].filter(Boolean).join("/");
  const q = new URLSearchParams();
  const put = (k: string, v: string | number | undefined) => {
    if (v !== undefined) q.set(k, String(v));
  };
  put("koszt_od", state.monthlyMin);
  put("koszt_do", state.monthlyMax);
  put("najem_od", state.rentMin);
  put("najem_do", state.rentMax);
  put("na_start_do", state.moveInMax);
  put("pokoje_od", state.roomsMin);
  put("metraz_od", state.areaMin);
  put("umeblowanie", state.furnished && FURNISHED_SLUG[state.furnished]);
  put("parking", state.parking && PARKING_SLUG[state.parking]);
  put("zwierzeta", state.pets ? "tak" : undefined);
  put("winda", state.elevator ? "tak" : undefined);
  put("dostepne_do", state.availableBy);
  put("okres_do", state.termMax);
  put("mapa", state.bbox?.join(","));
  put("sort", state.sort !== "newest" ? SORT_SLUG[state.sort] : undefined);
  put("strona", state.page > 1 ? state.page : undefined);
  put("widok", state.view === "map" ? "mapa" : undefined);
  const query = q.toString();
  return query ? `${path}?${query}` : path;
}

/** A changed search starts again from page 1. */
export function changed(state: SearchState, patch: Partial<SearchState>): SearchState {
  const next: SearchState = { ...state, ...patch, page: "page" in patch ? (patch.page ?? 1) : 1 };
  for (const key of Object.keys(next) as (keyof SearchState)[]) if (next[key] === undefined) delete next[key];
  return next;
}

/** Filters a user set (for "Filtry (3)" and the removable chips). Place, sort, page and view are not filters. */
export const FILTER_KEYS = ["monthlyMin", "monthlyMax", "rentMin", "rentMax", "moveInMax", "roomsMin", "areaMin", "furnished", "parking", "pets", "elevator", "availableBy", "termMax", "bbox"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];

export function activeFilters(state: SearchState): FilterKey[] {
  return FILTER_KEYS.filter((k) => state[k] !== undefined);
}

/** Whether the page is the bare city/area page (the only indexable results). */
export function isBare(state: SearchState): boolean {
  return activeFilters(state).length === 0 && state.sort === "newest" && state.page === 1 && state.view === "list";
}

export interface PlaceIds {
  localityId?: string;
  areaId?: string;
}

/** API query (minor units) for /v1/classifieds and /v1/classifieds/map. */
export function apiQuery(state: SearchState, place: PlaceIds): Record<string, string | number | boolean | string[]> {
  const q: Record<string, string | number | boolean | string[]> = { country_code: "PL" };
  if (place.localityId) q.locality_id = [place.localityId];
  if (place.areaId) q.geo_area_id = [place.areaId];
  const minor = (v: number | undefined) => (v === undefined ? undefined : v * 100);
  const set = (k: string, v: string | number | boolean | undefined) => {
    if (v !== undefined) q[k] = v;
  };
  set("min_monthly_total", minor(state.monthlyMin));
  set("max_monthly_total", minor(state.monthlyMax));
  set("min_rent", minor(state.rentMin));
  set("max_rent", minor(state.rentMax));
  set("max_move_in_total", minor(state.moveInMax));
  set("min_rooms", state.roomsMin);
  set("min_area_m2", state.areaMin);
  set("furnished", state.furnished);
  set("parking", state.parking);
  set("pets_allowed", state.pets);
  set("has_elevator", state.elevator);
  set("available_by", state.availableBy);
  set("max_term_months", state.termMax);
  set("bbox", state.bbox?.join(","));
  if (state.sort !== "newest") q.sort = state.sort;
  return q;
}
