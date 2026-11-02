import Link from "next/link";
import { cache, Suspense } from "react";

import { ListingCard } from "@/components/listing/listing-card";
import { SearchBox } from "@/components/search-box/search-box";
import { HomeAreas } from "@/components/home-areas";
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
      <div className={styles.intro}>
        <section className={styles.search} aria-labelledby="home-heading">
          <p className={styles.eyebrow}>{t.home.eyebrow}</p>
          <h1 id="home-heading" className={styles.title}>{t.home.heading}</h1>
          <p className={styles.lead}>{t.home.lead}</p>
          <SearchBox />
        </section>
        <Suspense fallback={<HomeAreas areas={[]} loading />}>
          <KrakowAreas />
        </Suspense>
      </div>
      <ul className={styles.pillars}>
        <li>{t.home.pillars.fullCost}</li>
        <li>{t.home.pillars.fresh}</li>
        <li>{t.home.pillars.free}</li>
      </ul>
      <Suspense fallback={<RailSkeleton />}>
        <NewestRail />
      </Suspense>
      <section className={styles.costs} aria-labelledby="koszty">
        <div>
          <p className={styles.eyebrow}>{t.home.costs.eyebrow}</p>
          <h2 id="koszty">{t.home.costs.heading}</h2>
          <p>{t.home.costs.body}</p>
        </div>
        <dl className={styles.costRows}>
          <div><dt>{t.home.costs.monthly}</dt><dd>{t.home.costs.monthlyBody}</dd></div>
          <div><dt>{t.home.costs.start}</dt><dd>{t.home.costs.startBody}</dd></div>
        </dl>
      </section>
      <section className={styles.owner} aria-labelledby="dla-wlascicieli">
        <h2 id="dla-wlascicieli">{t.addListing.heading}</h2>
        <p>{t.addListing.body}</p>
      </section>
    </div>
  );
}

// Share public reference resolution between independently streamed sections.
const krakow = cache(async () => {
  try { return await resolvePlace("krakow", undefined); }
  catch { return null; }
});

async function KrakowAreas() {
  const place = await krakow();
  return <HomeAreas areas={place?.areas ?? []} />;
}

async function newestInKrakow() {
  try {
    const place = await krakow();
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
