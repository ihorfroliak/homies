"use client";

import dynamic from "next/dynamic";

import { t } from "@/i18n";

import styles from "./results.module.css";

/** maplibre-gl is loaded only in map mode, never in the first view of other pages (FE-001 budget). */
export const MapLoader = dynamic(() => import("./map-canvas").then((m) => m.MapCanvas), {
  ssr: false,
  loading: () => (
    <div className={styles.mapCanvas} role="status">
      {t.map.loading}
    </div>
  ),
});
