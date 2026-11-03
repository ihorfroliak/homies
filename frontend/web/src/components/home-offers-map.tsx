"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { MapSection } from "@/app/wynajem/[[...miejsce]]/map-section";
import { t } from "@/i18n";
import type { MapPage, Locality } from "@/search/server";

import styles from "./home-explorer.module.css";

const state = { city: "krakow", sort: "newest", page: 1, view: "map" } as const;

/** Public city preview, independent of the not-yet-submitted search form.
 * Resolve the actual locality ID; never broaden to nationwide on a failed lookup. */
export function HomeOffersMap() {
  const [attempt, setAttempt] = useState(0);
  return (
    <section className={styles.offers} aria-labelledby="home-offers-heading">
      <h2 id="home-offers-heading">{t.home.explorer.heading}</h2>
      <p>{t.home.explorer.preview}</p>
      {!process.env.NEXT_PUBLIC_MAP_STYLE_URL ? <p>{t.home.explorer.noBasemap}</p> : null}
      <PublicMap key={attempt} retry={() => setAttempt((previous) => previous + 1)} />
      <Link className={styles.link} href="/wynajem/krakow?widok=mapa">{t.home.explorer.fullSearch}</Link>
    </section>
  );
}

function PublicMap({ retry }: { retry: () => void }) {
  const [result, setResult] = useState<{ data?: MapPage; failed?: boolean } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    async function read() {
      const options = { signal: controller.signal, headers: { accept: "application/json" } };
      const cityResponse = await fetch("/bff/v1/geo/localities/by-slug?country=PL&slug=krakow", options);
      if (!cityResponse.ok) throw new Error("locality unavailable");
      const cities = await cityResponse.json() as Locality[];
      const city = cities.find((row) => row.kind === "CITY" && row.slug === "krakow");
      if (!city) throw new Error("locality not found");
      const response = await fetch(`/bff/v1/classifieds/map?locality_id=${encodeURIComponent(city.id)}`, options);
      if (!response.ok) throw new Error("map unavailable");
      const data = await response.json() as MapPage;
      if (!controller.signal.aborted) setResult({ data });
    }
    void read().catch(() => { if (!controller.signal.aborted) setResult({ failed: true }); });
    return () => controller.abort();
  }, []);

  if (!result) return <p role="status">{t.map.loading}</p>;
  if (result.failed) return <div role="status"><p>{t.map.unavailable}</p><button className="btn btn--secondary" type="button" onClick={retry}>{t.home.explorer.retry}</button></div>;
  if (result.data?.total === 0) return <p role="status">{t.home.explorer.empty}</p>;
  return <MapSection state={state} place={{ areas: [] }} initial={result.data} />;
}
