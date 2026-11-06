"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { getVersion, LngLatBounds, Map as MapLibre, Marker, NavigationControl, setWorkerUrl, type StyleSpecification } from "maplibre-gl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { components } from "@/api/schema";
import { fmt, formatMoney, plural, t } from "@/i18n";
import { searchHref, type SearchState } from "@/search/codec";

import { MapCard } from "./map-card";
import { groupOverlaps, selectionStillValid } from "./map-groups";
import styles from "./results.module.css";

type MapPoint = components["schemas"]["MapPoint"];

/**
 * The map is provider-agnostic and development-only sourced (G-11): with no
 * NEXT_PUBLIC_MAP_STYLE_URL it draws a plain background — the public cells and
 * price pills still work, nothing is fetched from a tile server. OSM's public
 * tile servers are never used.
 *
 * Points sharing one public grid cell are a STACK ("4 oferty"), never
 * spiderfied into invented positions. Stacks whose pills would overlap at the
 * current zoom are drawn as one pill at a real member's position (map-groups);
 * no coordinate moves and zooming in separates them again. A pan or zoom never
 * re-queries silently: "Szukaj w tym obszarze" appears and makes the bbox an
 * explicit, removable filter.
 */
const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#e8eef2" } }],
};

const POLAND: [[number, number], [number, number]] = [[14.1, 49.0], [24.2, 54.9]];
/** Enough to separate neighbouring public cells without implying an exact address. */
const ZOOM_HERE_MAX = 17;

interface Stack {
  key: string;
  lat: number;
  lon: number;
  points: MapPoint[];
}

/** What an open card shows: the listings behind the pressed pill. */
interface Selection {
  stacks: Stack[];
  ids: string[];
}

function stacks(points: MapPoint[]): Stack[] {
  const byCell = new Map<string, Stack>();
  for (const p of points) {
    const key = `${p.latitude.toFixed(5)},${p.longitude.toFixed(5)}`;
    const s = byCell.get(key) ?? { key, lat: p.latitude, lon: p.longitude, points: [] };
    s.points.push(p);
    byCell.set(key, s);
  }
  return [...byCell.values()];
}

function pillText(p: MapPoint): string {
  return p.monthly_total_estimate !== null ? formatMoney(p.monthly_total_estimate) : p.rent_amount !== null ? formatMoney(p.rent_amount) : "—";
}

function drawPill(el: HTMLElement, members: Stack[]) {
  const total = members.reduce((n, s) => n + s.points.length, 0);
  const label = total > 1 ? plural(t.plural.listings, total) : pillText(members[0]!.points[0]!);
  el.textContent = label;
  el.dataset.kind = members.length > 1 ? "nearby" : total > 1 ? "stack" : "price";
  el.setAttribute("aria-label", members.length > 1 ? fmt(t.map.nearby, { count: label }) : total > 1 ? fmt(t.map.stack, { count: label }) : fmt(t.card.monthly, { amount: label }));
}

export function MapCanvas({ state, points, areaName }: { state: SearchState; points: MapPoint[]; areaName?: string }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibre | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const openSelection = useRef<Selection | null>(null);
  const router = useRouter();
  const [moved, setMoved] = useState(false);
  // No WebGL: the list is the fallback (decided once, before the map is built).
  const [failed, setFailed] = useState(() => typeof document !== "undefined" && !document.createElement("canvas").getContext("webgl2") && !document.createElement("canvas").getContext("webgl"));
  const [selected, setSelected] = useState<Selection | null>(null);
  const groups = useMemo(() => stacks(points), [points]);
  // Map events run outside React and must read the card that is open right now.
  const select = useCallback((next: Selection | null) => {
    openSelection.current = next;
    setSelected(next);
  }, []);

  useEffect(() => {
    if (!container.current || failed) return;
    // The worker is served same-origin from public/vendor (scripts/copy-map-worker.mjs).
    setWorkerUrl(`/vendor/maplibre-gl-${getVersion()}/maplibre-gl-worker.mjs`);
    const map = new MapLibre({
      container: container.current,
      style: process.env.NEXT_PUBLIC_MAP_STYLE_URL || BLANK_STYLE,
      bounds: state.bbox ? [[state.bbox[0], state.bbox[1]], [state.bbox[2], state.bbox[3]]] : POLAND,
      // Configured development styles supply attribution through their sources.
      // Keep it accessible on small maps; a blank style has no source credits.
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      cooperativeGestures: false,
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("error", () => setFailed((f) => f || !map.loaded()));

    const entries = groups.map((group) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = styles.pill ?? "";
      el.dataset.cell = group.key;
      return { group, el, marker: new Marker({ element: el, anchor: "bottom" }).setLngLat([group.lon, group.lat]).addTo(map) };
    });
    const members = new Map<HTMLElement, Stack[]>();
    const ownerOf = new Map<string, HTMLElement>();

    const regroup = () => {
      // Measure every stack as itself first: a group's own label must not decide who overlaps.
      for (const e of entries) {
        e.el.style.display = "";
        drawPill(e.el, [e.group]);
      }
      const byKey = new Map(entries.map((e) => [e.group.key, e]));
      const clusters = groupOverlaps(entries.map((e) => {
        const at = map.project([e.group.lon, e.group.lat]);
        return { key: e.group.key, x: at.x, y: at.y, w: e.el.offsetWidth, h: e.el.offsetHeight, weight: e.group.points.length };
      }));
      members.clear();
      ownerOf.clear();
      for (const cluster of clusters) {
        const shown = byKey.get(cluster.representative)!;
        const included = cluster.members.map((k) => byKey.get(k)!.group);
        drawPill(shown.el, included);
        members.set(shown.el, included);
        for (const s of included) for (const p of s.points) ownerOf.set(p.id, shown.el);
        for (const k of cluster.members) if (k !== cluster.representative) byKey.get(k)!.el.style.display = "none";
      }
      // A card names a group. If zoom or resize dissolved that group, the card goes too,
      // and focus held inside it moves to the pill now showing its first listing.
      const open = openSelection.current;
      if (open && !selectionStillValid(open.stacks.map((s) => s.key), clusters)) {
        const focusInCard = document.activeElement?.closest('[role="dialog"]')?.parentElement === container.current?.parentElement;
        select(null);
        if (focusInCard) {
          const holder = clusters.find((c) => c.members.includes(open.stacks[0]!.key));
          (holder ? byKey.get(holder.representative)!.el : map.getCanvas()).focus({ preventScroll: true });
        }
      }
    };

    for (const { el } of entries) {
      el.addEventListener("click", () => {
        const included = members.get(el);
        if (!included) return;
        opener.current = el;
        select({ stacks: included, ids: included.flatMap((s) => s.points.map((p) => p.id)) });
      });
    }

    if (!state.bbox && groups.length > 0) {
      const bounds = new LngLatBounds();
      for (const g of groups) bounds.extend([g.lon, g.lat]);
      map.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 0 });
    }
    regroup();
    map.on("zoomend", regroup);
    map.on("resize", regroup);

    const onMove = (e: { originalEvent?: unknown }) => {
      if (e.originalEvent) setMoved(true); // user gestures only, not fitBounds
    };
    map.on("moveend", onMove);
    map.on("click", (e) => {
      // A pressed pill also reaches the map as a click: only the empty map closes the card.
      if (e.originalEvent.target instanceof Element && e.originalEvent.target.closest("button")) return;
      select(null);
    });

    // A card under the pointer or keyboard focus marks its pill, so list and map read as one.
    const results = document.getElementById("wyniki");
    let active: HTMLElement | undefined;
    const mark = (id?: string) => {
      const next = id ? ownerOf.get(id) : undefined;
      if (next === active) return;
      if (active) delete active.dataset.active;
      if (next) next.dataset.active = "true";
      active = next;
    };
    const onCard = (event: Event) => {
      const card = event.target instanceof Element ? event.target.closest("article") : null;
      mark(card?.querySelector<HTMLElement>("[data-listing-id]")?.dataset.listingId);
    };
    const onLeave = () => mark();
    results?.addEventListener("mouseover", onCard);
    results?.addEventListener("focusin", onCard);
    results?.addEventListener("mouseleave", onLeave);
    results?.addEventListener("focusout", onLeave);

    return () => {
      results?.removeEventListener("mouseover", onCard);
      results?.removeEventListener("focusin", onCard);
      results?.removeEventListener("mouseleave", onLeave);
      results?.removeEventListener("focusout", onLeave);
      for (const e of entries) e.marker.remove();
      map.remove();
      mapRef.current = null;
    };
  }, [groups, state.bbox, failed, select]);

  const searchHere = () => {
    const map = mapRef.current;
    if (!map) return;
    const b = map.getBounds();
    const r = (v: number) => Math.round(v * 1e6) / 1e6;
    router.push(searchHref({ ...state, bbox: [r(b.getWest()), r(b.getSouth()), r(b.getEast()), r(b.getNorth())], page: 1, view: "map" }));
  };

  // Focus returns to the pill that opened the card, or to the map if a zoom regrouped it away.
  const closeCard = () => {
    select(null);
    const back = opener.current;
    if (back?.isConnected && back.style.display !== "none") back.focus({ preventScroll: true });
    else mapRef.current?.getCanvas().focus({ preventScroll: true });
  };

  const zoomHere = () => {
    const map = mapRef.current;
    if (!map || !selected) return;
    const bounds = new LngLatBounds();
    for (const s of selected.stacks) bounds.extend([s.lon, s.lat]);
    map.fitBounds(bounds, { padding: 96, maxZoom: ZOOM_HERE_MAX });
    select(null);
    map.getCanvas().focus({ preventScroll: true });
  };

  if (failed) {
    return (
      <div className="alert alert--warning" role="status">
        <p>{t.map.unavailable}</p>
        <Link href={searchHref({ ...state, view: "list" })}>{t.map.switchToList}</Link>
      </div>
    );
  }

  return (
    <div className={styles.mapWrap}>
      <div ref={container} className={styles.mapCanvas} role="region" aria-label={areaName ? `${t.map.label}: ${areaName}` : t.map.label} />
      {moved ? (
        <button type="button" className={`btn btn--primary ${styles.searchHere}`} onClick={searchHere}>
          {t.map.searchHere}
        </button>
      ) : null}
      {selected ? <MapCard key={selected.ids.join()} ids={selected.ids} nearby={selected.stacks.length > 1} onClose={closeCard} onZoom={selected.stacks.length > 1 ? zoomHere : undefined} /> : null}
    </div>
  );
}
