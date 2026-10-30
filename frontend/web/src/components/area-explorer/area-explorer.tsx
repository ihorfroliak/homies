import Link from "next/link";

import { t } from "@/i18n";

import { areaHue } from "./area-colour";
import styles from "./area-explorer.module.css";

export interface ExplorerArea {
  id: string;
  name: string;
  slug?: string | null;
}

/**
 * "Kraków po okolicach" (DESIGN-001C Home Mapa, HM-1, FE-VIS-001A): the city's
 * real areas from the geo API as links into their results
 * (`/wynajem/{city}/{area}`), plus the whole city. An area without a slug has
 * no route yet and is not linked (HM-1.5). No counts — none can be sourced
 * without one query per area (HM-1.7). The colour is place identity only
 * (D-103), said in words under the heading. The drawn district map of the
 * design waits for an approved boundary source and licence (001C MASTER open
 * decisions 1–2); this list is the keyboard way in that the map adds to.
 */
export function AreaExplorer({ citySlug, areas }: { citySlug: string; areas: ExplorerArea[] }) {
  const linked = areas.filter((a): a is ExplorerArea & { slug: string } => Boolean(a.slug));
  return (
    <section className={styles.explorer} aria-labelledby="okolice">
      <h2 id="okolice" className={styles.heading}>{t.areas.heading}</h2>
      <p className={styles.note}>{t.areas.colourNote}</p>
      <ul className={styles.grid}>
        {linked.map((area) => (
          <li key={area.id}>
            <Link href={`/wynajem/${citySlug}/${area.slug}`} className={styles.tile} data-hue={areaHue(area.slug)}>
              <span className={styles.name}>{area.name}</span>
              <span className={styles.arrow} aria-hidden="true">→</span>
            </Link>
          </li>
        ))}
        <li className={styles.wholeCity}>
          <Link href={`/wynajem/${citySlug}`} className={`${styles.tile} ${styles.all}`}>
            <span className={styles.name}>{t.areas.all}</span>
            <span className={styles.arrow} aria-hidden="true">→</span>
          </Link>
        </li>
      </ul>
    </section>
  );
}
