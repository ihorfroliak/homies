"use client";

import { useEffect } from "react";

import { browserAnalytics, rememberClick, takeSearchRef } from "./client";

/** search_performed (new canonical query) + search_results_viewed; remembers which card was opened. */
export function SearchTracker(props: {
  searchId: string;
  route: string;
  dimensions: string[];
  localityId?: string;
  areaId?: string;
  sort: string;
  resultCount: number;
  pageIndex: number;
  visibleCount: number;
  priceBand?: number;
  surface: "list" | "map";
  containerId: string;
}) {
  const { searchId, route, dimensions, localityId, areaId, sort, resultCount, pageIndex, visibleCount, priceBand, surface, containerId } = props;
  useEffect(() => {
    const { analytics } = browserAnalytics();
    analytics.track(
      "search_performed",
      { search_id: searchId, filter_dimensions: dimensions, locality_id: localityId, area_id: areaId, sort, result_count: resultCount, price_band: priceBand, surface },
      { route },
    );
    analytics.track("search_results_viewed", { search_id: searchId, page_index: pageIndex, visible_count: visibleCount }, { route });
    if (surface === "map") analytics.track("map_mode_entered", { search_id: searchId }, { route });
    // One effect per canonical query (searchId is minted per render of a query).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchId]);

  useEffect(() => {
    const container = document.getElementById(containerId);
    if (!container) return;
    const onClick = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest<HTMLElement>("[data-listing-id]");
      if (!link?.dataset.listingId) return;
      rememberClick(searchId, link.dataset.listingId, link.dataset.position ? Number(link.dataset.position) : undefined);
    };
    container.addEventListener("click", onClick);
    return () => container.removeEventListener("click", onClick);
  }, [containerId, searchId]);
  return null;
}

export function ListingViewTracker({ listingId }: { listingId: string }) {
  useEffect(() => {
    const ref = takeSearchRef(listingId);
    browserAnalytics().analytics.track("listing_viewed", { listing_id: listingId, search_id: ref.searchId, position: ref.position }, { route: "/oferta/[id]" });
  }, [listingId]);
  return null;
}
