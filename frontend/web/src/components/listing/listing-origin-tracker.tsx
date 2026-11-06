"use client";

import { useEffect } from "react";

import { canonicalOrigin, recordOrigin } from "@/search/last-results";

/**
 * Notes where a listing link was followed from, in one place for every surface that
 * shows one (cards, map cards, the saved list, the home page). Capture phase: it must
 * run before the client navigation changes the location. A link to the listing already
 * on screen, such as its retry, is not a new origin.
 */
export function ListingOriginTracker() {
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a[href^="/oferta/"]') : null;
      if (!link || link.pathname === window.location.pathname) return;
      const id = link.pathname.split("/")[2];
      if (id) recordOrigin(id, canonicalOrigin(window.location.pathname, window.location.search));
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);
  return null;
}
