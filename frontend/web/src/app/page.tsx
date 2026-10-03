import Link from "next/link";
import { Suspense } from "react";

import { ListingCard } from "@/components/listing/listing-card";
import { SearchBox } from "@/components/search-box/search-box";
import { t } from "@/i18n";
import { newest, resolvePlace } from "@/search/server";

import styles from "./page.module.css";

/**
 * Home (DESIGN-001 §5.1): positioning, the search box, three factual pillars,
 * the newest real listings in Kraków (launch city), and the owner note. No
 * invented market statistics. The rail streams in; on any error it is simply
 * not shown (never a broken rail).
 */
export default function HomePage() {
  return (
    <div className={`container ${styles.hero}`}>
      <h1 className={styles.title}>{t.home.heading}</h1>
      <p className={styles.lead}>{t.home.lead}</p>
      <SearchBox />
      <ul className={styles.pillars}>
        <li>{t.home.pillars.fullCost}</li>
        <li>{t.home.pillars.fresh}</li>
        <li>{t.home.pillars.free}</li>
      </ul>
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

async function newestInKrakow() {
  try {
    const place = await resolvePlace("krakow", undefined);
    return place?.localityId ? await newest({ localityId: place.localityId }, 6) : [];
  } catch {
    return [];
  }
}

async function NewestRail() {
  const items = await newestInKrakow();
  if (items.length === 0) return null;
  return (
    <section className={styles.rail} aria-labelledby="najnowsze">
      <h2 id="najnowsze">{t.newest.heading}</h2>
      <ul className={styles.railList}>
        {items.map((l) => (
          <li key={l.id}>
            <ListingCard listing={l} />
          </li>
        ))}
      </ul>
      <Link href="/wynajem/krakow">{t.newest.seeAll}</Link>
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
