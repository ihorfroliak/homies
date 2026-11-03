"use client";

import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";

import { t } from "@/i18n";

import styles from "./home-explorer.module.css";

// Neither the map engine nor its public API requests run before explicit choice.
const OffersMap = dynamic(() => import("./home-offers-map").then((m) => m.HomeOffersMap), {
  loading: () => <p role="status">{t.map.loading}</p>,
});

export function HomeExplorer({ children }: { children: ReactNode }) {
  const [offers, setOffers] = useState(false);
  return (
    <div className={styles.explorer}>
      <div className={styles.switcher} role="group" aria-label={t.home.explorer.label}>
        <button type="button" aria-pressed={!offers} aria-controls="home-districts" onClick={() => setOffers(false)}>{t.home.explorer.districts}</button>
        <button type="button" aria-pressed={offers} aria-controls="home-offers" onClick={() => setOffers(true)}>{t.home.explorer.offers}</button>
      </div>
      <div id="home-districts" hidden={offers}>{children}</div>
      <div id="home-offers" hidden={!offers}>{offers ? <OffersMap /> : null}</div>
    </div>
  );
}
