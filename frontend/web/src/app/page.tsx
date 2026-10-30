import Link from "next/link";
import { Suspense } from "react";

import { AreaExplorer } from "@/components/area-explorer/area-explorer";
import { HomeSearch } from "@/components/home-search/home-search";
import { ListingCard } from "@/components/listing/listing-card";
import { t } from "@/i18n";
import { newest, resolvePlace } from "@/search/server";

import styles from "./page.module.css";

const LAUNCH_CITY = { slug: "krakow", name: "Kraków" } as const;

/**
 * Home (DESIGN-001C Home Mapa / HM-1, FE-VIS-001A): positioning and the search
 * form on the left; "Kraków po okolicach" on the right from 1024 px, or as its
 * own full-width section below the search on smaller screens; the newest real
 * listings in Kraków; the owner note. No invented statistics or counts.
 * Streamed sections never break the page: without areas the form still
 * searches the whole city, and the rail is simply not shown on an error.
 */
export default function HomePage() {
  return (
    <div className={`container ${styles.home}`}>
      <div className={styles.hero}>
        <div className={styles.intro}>
          <p className={styles.eyebrow}>{t.home.eyebrow}</p>
          <h1 className={styles.title}>{t.home.heading}</h1>
          <p className={styles.lead}>{t.home.lead}</p>
          <Suspense fallback={<HomeSearch cityName={LAUNCH_CITY.name} areas={[]} />}>
            <SearchWithAreas />
          </Suspense>
          <ul className={styles.pillars}>
            <li>{t.home.pillars.fullCost}</li>
            <li>{t.home.pillars.fresh}</li>
            <li>{t.home.pillars.free}</li>
          </ul>
        </div>
        <Suspense fallback={<div className={`skeleton ${styles.explorerSkeleton}`} aria-hidden="true" />}>
          <LaunchCityAreas />
        </Suspense>
      </div>
      <Suspense fallback={<RailSkeleton />}>
        <NewestRail />
      </Suspense>
      <section className={styles.owner} aria-labelledby="dla-wlascicieli">
        <h2 id="dla-wlascicieli">{t.addListing.heading}</h2>
        <p>{t.addListing.body}</p>
      </section>
    </div>
  );
}

async function launchCity() {
  try {
    return await resolvePlace(LAUNCH_CITY.slug, undefined);
  } catch {
    return null;
  }
}

async function SearchWithAreas() {
  const place = await launchCity();
  return <HomeSearch cityName={LAUNCH_CITY.name} areas={place?.areas ?? []} />;
}

async function LaunchCityAreas() {
  const place = await launchCity();
  return <AreaExplorer citySlug={LAUNCH_CITY.slug} areas={place?.areas ?? []} />;
}

async function NewestRail() {
  const place = await launchCity();
  let items: Awaited<ReturnType<typeof newest>> = [];
  try {
    items = place?.localityId ? await newest({ localityId: place.localityId }, 6) : [];
  } catch {
    items = [];
  }
  if (items.length === 0) return null;
  return (
    <section className={styles.rail} aria-labelledby="najnowsze">
      <div className={styles.railHead}>
        <h2 id="najnowsze">{t.newest.heading}</h2>
        <Link href={`/wynajem/${LAUNCH_CITY.slug}`}>{t.newest.seeAll}</Link>
      </div>
      <ul className={styles.railList}>
        {items.map((l) => (
          <li key={l.id}>
            <ListingCard listing={l} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function RailSkeleton() {
  return (
    <div className={styles.rail} aria-hidden="true">
      <ul className={styles.railList}>
        {[0, 1, 2].map((i) => (
          <li key={i} className={`skeleton ${styles.skeletonCard}`} />
        ))}
      </ul>
    </div>
  );
}
