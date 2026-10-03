import { t } from "@/i18n";

import styles from "./page.module.css";

/**
 * Home (DESIGN-001 §5.1). FE-001 renders the static, factual frame; FE-002 adds
 * the search box (city + max monthly cost) and the "Najnowsze" rail from the
 * real API. No invented market statistics.
 */
export default function HomePage() {
  return (
    <div className={`container ${styles.hero}`}>
      <h1 className={styles.title}>{t.home.heading}</h1>
      <p className={styles.lead}>{t.home.lead}</p>
      <ul className={styles.pillars}>
        <li>{t.home.pillars.fullCost}</li>
        <li>{t.home.pillars.fresh}</li>
        <li>{t.home.pillars.free}</li>
      </ul>
    </div>
  );
}
