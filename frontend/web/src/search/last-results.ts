import { parseSearch, searchHref } from "./codec";

/**
 * Where the listing on screen was opened from, per tab. The record names the
 * listing, so an earlier search is never offered for a listing that did not come
 * from it. Storage is untrusted: only a canonical results URL or the saved list is
 * ever used as a link, and only for that listing.
 */
const KEY = "homies.search.listing-origin";
const SAVED = "/zapisane";
const MAX_LENGTH = 2048;
const RESULTS = /^\/wynajem((?:\/[a-z0-9-]+){0,2})(?:\?([^#]*))?$/;

export type ListingOrigin = { path: string; kind: "results" | "saved" };

/**
 * A stored value counts only if the search codec would produce exactly it. Anything
 * else (encoded separators, dot segments, foreign parameters, reordered queries) is
 * not a URL this application generated, whatever a browser might normalise it to.
 */
export function safeReturnPath(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length > MAX_LENGTH) return undefined;
  if (value === SAVED) return value;
  const match = RESULTS.exec(value);
  if (!match) return undefined;
  const parsed = parseSearch((match[1] ?? "").split("/").filter(Boolean), new URLSearchParams(match[2] ?? ""));
  if (parsed.badPath || parsed.dropped.length > 0) return undefined;
  return searchHref(parsed.state) === value ? value : undefined;
}

/** The canonical origin for the page at this location, if it is one a listing can return to. */
export function canonicalOrigin(pathname: string, search: string): string | undefined {
  if (pathname === SAVED) return SAVED;
  if (pathname !== "/wynajem" && !pathname.startsWith("/wynajem/")) return undefined;
  const parsed = parseSearch(pathname.split("/").slice(2).filter(Boolean), new URLSearchParams(search));
  return parsed.badPath ? undefined : safeReturnPath(searchHref(parsed.state));
}

/** Records the origin of a listing being opened; no origin forgets any earlier one. */
export function recordOrigin(listing: string, path: string | undefined): void {
  try {
    const safe = safeReturnPath(path);
    if (safe) sessionStorage.setItem(KEY, JSON.stringify({ listing, path: safe }));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* Without storage the listing offers its city. */
  }
}

export function originFor(listing: string): ListingOrigin | undefined {
  try {
    const stored: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
    if (!stored || typeof stored !== "object") return undefined;
    const record = stored as { listing?: unknown; path?: unknown };
    if (record.listing !== listing) return undefined;
    const path = safeReturnPath(record.path);
    return path ? { path, kind: path === SAVED ? "saved" : "results" } : undefined;
  } catch {
    return undefined;
  }
}
