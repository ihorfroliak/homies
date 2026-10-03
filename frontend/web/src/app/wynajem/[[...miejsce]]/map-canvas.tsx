"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { LngLatBounds, Map as MapLibre, Marker, NavigationControl, type StyleSpecification } from "maplibre-gl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import type { components } from "@/api/schema";
import { coverOf, monthlyLabel, placeLabel } from "@/components/listing/format";
import { fmt, formatMoney, plural, t } from "@/i18n";
import { searchHref, type SearchState } from "@/search/codec";

import styles from "./results.module.css";

type MapPoint = components["schemas"]["MapPoint"];
type Classified = components["schemas"]["ClassifiedOut"];

/**
 * The map is provider-agnostic and development-only sourced (G-11): with no
 * NEXT_PUBLIC_MAP_STYLE_URL it draws a plain background — the public cells and
 * price pills still work, nothing is fetched from a tile server. OSM's public
 * tile servers are never used.
 *
 * Points sharing one public grid cell are a STACK ("4 oferty"), never
 * spiderfied into invented positions. A pan or zoom never re-queries silently:
 * "Szukaj w tym obszarze" appears and makes the bbox an explicit, removable
 * filter.
 */
const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#e8eef2" } }],
};

const POLAND: [[number, number], [number, number]] = [[14.1, 49.0], [24.2, 54.9]];

interface Stack {
  key: string;
  lat: number;
  lon: number;
  points: MapPoint[];
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

export function MapCanvas({ state, points, areaName }: { state: SearchState; points: MapPoint[]; areaName?: string }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibre | null>(null);
  const router = useRouter();
  const [moved, setMoved] = useState(false);
  // No WebGL: the list is the fallback (decided once, before the map is built).
  const [failed, setFailed] = useState(() => typeof document !== "undefined" && !document.createElement("canvas").getContext("webgl2") && !document.createElement("canvas").getContext("webgl"));
  const [selected, setSelected] = useState<Stack | null>(null);
  const groups = useMemo(() => stacks(points), [points]);

  useEffect(() => {
    if (!container.current || failed) return;
    const map = new MapLibre({
      container: container.current,
      style: process.env.NEXT_PUBLIC_MAP_STYLE_URL || BLANK_STYLE,
      bounds: state.bbox ? [[state.bbox[0], state.bbox[1]], [state.bbox[2], state.bbox[3]]] : POLAND,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      cooperativeGestures: false,
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("error", () => setFailed((f) => f || !map.loaded()));
    const markers: Marker[] = [];
    for (const group of groups) {
      const el = document.createElement("button");
      el.type = "button";
      el.className = styles.pill ?? "";
      const label = group.points.length > 1 ? plural(t.plural.listings, group.points.length) : `${pillText(group.points[0]!)}`;
      el.textContent = label;
      el.setAttribute("aria-label", group.points.length > 1 ? fmt(t.map.stack, { count: label }) : fmt(t.card.monthly, { amount: label }));
      el.addEventListener("click", () => setSelected(group));
      markers.push(new Marker({ element: el, anchor: "bottom" }).setLngLat([group.lon, group.lat]).addTo(map));
    }
    if (!state.bbox && groups.length > 0) {
      const bounds = new LngLatBounds();
      for (const g of groups) bounds.extend([g.lon, g.lat]);
      map.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 0 });
    }
    const onMove = (e: { originalEvent?: unknown }) => {
      if (e.originalEvent) setMoved(true); // user gestures only, not fitBounds
    };
    map.on("moveend", onMove);
    return () => {
      for (const m of markers) m.remove();
      map.remove();
      mapRef.current = null;
    };
  }, [groups, state.bbox, failed]);

  const searchHere = () => {
    const map = mapRef.current;
    if (!map) return;
    const b = map.getBounds();
    const r = (v: number) => Math.round(v * 1e6) / 1e6;
    router.push(searchHref({ ...state, bbox: [r(b.getWest()), r(b.getSouth()), r(b.getEast()), r(b.getNorth())], page: 1, view: "map" }));
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
      {selected ? <MapCard stack={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

/** MapPoint has no title or cover (gap G5): the card reads the public detail through the BFF. */
function MapCard({ stack, onClose }: { stack: Stack; onClose: () => void }) {
  const [items, setItems] = useState<Classified[] | null>(null);
  const [error, setError] = useState(false);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    close.current?.focus();
    const controller = new AbortController();
    Promise.all(
      stack.points.slice(0, 10).map((p) =>
        fetch(`/bff/v1/classifieds/${encodeURIComponent(p.id)}`, { signal: controller.signal, headers: { accept: "application/json" } }).then((r) => (r.ok ? (r.json() as Promise<Classified>) : null)),
      ),
    )
      .then((rows) => setItems(rows.filter((r): r is Classified => r !== null)))
      .catch((e) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setError(true);
      });
    return () => controller.abort();
  }, [stack]);

  return (
    <div className={styles.mapCard} role="dialog" aria-modal="false" aria-label={plural(t.plural.listings, stack.points.length)} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <button ref={close} type="button" className="btn btn--ghost" onClick={onClose} aria-label={t.map.close}>
        ×
      </button>
      {error ? <p>{t.errors.unavailable}</p> : null}
      {!items && !error ? <p role="status">{t.a11y.loading}</p> : null}
      <ul className={styles.mapCardList}>
        {items?.map((l) => {
          const cover = coverOf(l);
          return (
            <li key={l.id}>
              {cover ? (
                // eslint-disable-next-line @next/next/no-img-element -- /v1/media must not go through the optimiser (FE-001 §5)
                <img src={cover.url} alt="" width={96} height={72} loading="lazy" />
              ) : null}
              <div>
                <p className={styles.mapCardPrice}>{monthlyLabel(l)}</p>
                <Link href={`/oferta/${l.id}`}>{l.title}</Link>
                <p className="small muted">{placeLabel(l)}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
