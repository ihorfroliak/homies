import "server-only";

import { cache } from "react";

import { ApiError, errorFromResponse } from "@/api/errors";
import type { components } from "@/api/schema";
import { backendClient, type CallContext } from "@/server/backend";
import { currentContext } from "@/server/bff";
import { TtlLru } from "@/server/lru";

import { FILTER_KEYS, MAX_OFFSET, PAGE_SIZE, apiQuery, changed, type FilterKey, type PlaceIds, type SearchState } from "./codec";

export type Classified = components["schemas"]["ClassifiedOut"];
export type ClassifiedPage = components["schemas"]["ClassifiedPage"];
export type MapPage = components["schemas"]["MapPage"];
export type Locality = components["schemas"]["LocalityOut"];
export type GeoArea = components["schemas"]["GeoAreaOut"];

/**
 * Server-side reads for the seeker slice. Public data, read anonymously (the
 * pages are the same for everyone, so no session is forwarded), with the end
 * user's IP and the request id forwarded for the backend rate limiter and logs.
 */
async function ctx(): Promise<CallContext> {
  const c = await currentContext();
  return { clientIp: c.clientIp, requestId: c.requestId };
}

type Result<T> = { data?: T; error?: unknown; response: Response };

async function unwrapServer<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    throw new ApiError({ kind: timedOut ? "timeout" : "network" });
  }
  if (result.response.ok && result.data !== undefined) return result.data;
  throw errorFromResponse("GET", result.response.status, result.response.headers, result.error);
}

// Reference data changes rarely. One resolution per city slug per 10 minutes
// per process, in a bounded LRU (SEC-002): the city's areas are cached with
// it, so an unknown area slug costs no backend call, and random slugs can
// neither grow memory without limit nor multiply backend calls.
const PLACE_TTL_MS = 10 * 60 * 1000;
const cities = new TtlLru<{ locality: Locality; areas: GeoArea[] } | null>(2_000, PLACE_TTL_MS);

export interface ResolvedPlace extends PlaceIds {
  locality?: Locality;
  area?: GeoArea;
  areas: GeoArea[];
}

async function city(slug: string): Promise<{ locality: Locality; areas: GeoArea[] } | null> {
  const hit = cities.get(slug);
  if (hit) return hit.value;
  const api = backendClient(await ctx());
  const matches = await unwrapServer(api.GET("/v1/geo/localities/by-slug", { params: { query: { country: "PL", slug } } }));
  // Slugs are not unique; the backend lists cities first. Only a city is a
  // result page; a village slug without a city is not resolved silently.
  const locality = matches.find((l) => l.kind === "CITY");
  const value = locality
    ? { locality, areas: await unwrapServer(api.GET("/v1/geo/localities/{locality_id}/areas", { params: { path: { locality_id: locality.id } } })) }
    : null;
  cities.set(slug, value);
  return value;
}

/** City/area slugs → ids. `null` = a slug that names nothing (the page answers 404). */
export async function resolvePlace(citySlug: string | undefined, area: string | undefined): Promise<ResolvedPlace | null> {
  if (!citySlug) return { areas: [] };
  const found = await city(citySlug);
  if (!found) return null;
  const match = area ? found.areas.find((a) => a.slug === area) : undefined;
  if (area && !match) return null;
  return { localityId: found.locality.id, areaId: match?.id, locality: found.locality, area: match, areas: found.areas };
}

export async function searchPage(state: SearchState, place: PlaceIds): Promise<ClassifiedPage> {
  const offset = Math.min((state.page - 1) * PAGE_SIZE, MAX_OFFSET);
  const api = backendClient(await ctx());
  return unwrapServer(api.GET("/v1/classifieds", { params: { query: { ...apiQuery(state, place), limit: PAGE_SIZE, offset } as never } }));
}

export async function mapPage(state: SearchState, place: PlaceIds): Promise<MapPage> {
  const api = backendClient(await ctx());
  return unwrapServer(api.GET("/v1/classifieds/map", { params: { query: apiQuery(state, place) as never } }));
}

export async function listing(id: string): Promise<Classified> {
  const api = backendClient(await ctx());
  return unwrapServer(api.GET("/v1/classifieds/{offer_id}", { params: { path: { offer_id: id } } }));
}

export async function newest(place: PlaceIds, limit: number): Promise<Classified[]> {
  const api = backendClient(await ctx());
  const page = await unwrapServer(api.GET("/v1/classifieds", { params: { query: { ...apiQuery({ sort: "newest", page: 1, view: "list" }, place), limit } as never } }));
  return page.items;
}

/** Decision-weight order (DESIGN-001 §5.4): suggestions remove the least important filter first. */
const RELAX_ORDER: FilterKey[] = ["elevator", "pets", "parking", "furnished", "termMax", "availableBy", "areaMin", "roomsMin", "moveInMax", "rentMin", "rentMax", "monthlyMin", "monthlyMax", "bbox"];

export interface Relaxation {
  remove: FilterKey;
  total: number;
}

/**
 * Zero results only: re-count with one filter removed, at most 3 parallel
 * `limit=1` calls, and keep those that would find something.
 */
export async function relaxations(state: SearchState, place: PlaceIds): Promise<Relaxation[]> {
  const candidates = RELAX_ORDER.filter((k) => FILTER_KEYS.includes(k) && state[k] !== undefined).slice(0, 3);
  if (candidates.length === 0) return [];
  const api = backendClient(await ctx());
  const counts = await Promise.allSettled(
    candidates.map((k) =>
      unwrapServer(api.GET("/v1/classifieds", { params: { query: { ...apiQuery(changed(state, { [k]: undefined }), place), limit: 1 } as never } })).then((p) => ({ remove: k, total: p.total })),
    ),
  );
  return counts.flatMap((c) => (c.status === "fulfilled" && c.value.total > 0 ? [c.value] : []));
}

/** API parameter → codec field, to drop what the backend refused (422). */
const API_TO_STATE: Record<string, keyof SearchState> = {
  min_monthly_total: "monthlyMin", max_monthly_total: "monthlyMax", min_rent: "rentMin", max_rent: "rentMax",
  max_move_in_total: "moveInMax", min_rooms: "roomsMin", min_area_m2: "areaMin", furnished: "furnished",
  parking: "parking", pets_allowed: "pets", has_elevator: "elevator", available_by: "availableBy",
  max_term_months: "termMax", bbox: "bbox", sort: "sort",
};

export interface Search {
  state: SearchState;
  page?: ClassifiedPage;
  error?: ApiError;
  /** Fields dropped because the backend refused them. */
  refused: string[];
}

/**
 * One list search per request (shared by generateMetadata and the page via
 * React `cache`). A 422 naming parameters the codec let through is answered by
 * one retry without them — never a redirect, so it can never loop.
 */
export const searchOnce = cache(async (key: string): Promise<Search> => {
  const { state, ids } = JSON.parse(key) as { state: SearchState; ids: PlaceIds };
  try {
    return { state, page: await searchPage(state, ids), refused: [] };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const fields = e.kind === "validation" ? e.invalid.map((p) => API_TO_STATE[p]).filter((f): f is keyof SearchState => f !== undefined) : [];
    if (fields.length === 0) return { state, error: e, refused: [] };
    const retry = changed(state, Object.fromEntries(fields.map((f) => [f, f === "sort" ? "newest" : undefined])) as Partial<SearchState>);
    try {
      return { state: retry, page: await searchPage(retry, ids), refused: fields };
    } catch (again) {
      if (again instanceof ApiError) return { state: retry, error: again, refused: fields };
      throw again;
    }
  }
});

export function searchKey(state: SearchState, ids: PlaceIds): string {
  return JSON.stringify({ state, ids });
}
