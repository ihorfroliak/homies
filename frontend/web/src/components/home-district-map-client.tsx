"use client";

import Link from "next/link";
import { useState, type CSSProperties, type ReactNode } from "react";

import { t } from "@/i18n";

import styles from "./home-district-map.module.css";

type District = { id: number; roman: string; name: string; hue: number };

export function DistrictExplorer({ districts, children }: { districts: District[]; children: ReactNode }) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = districts.find((district) => district.id === selectedId);
  return (
    <section className={styles.panel} aria-labelledby="district-map-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>{t.home.districtMap.eyebrow}</p>
          <h2 id="district-map-heading">{t.home.districtMap.heading}</h2>
        </div>
        <span className={styles.badge}>{t.home.districtMap.badge}</span>
      </header>
      <p className={styles.intro}>{t.home.districtMap.intro}</p>
      {/* Pointer shortcut only. The complete equivalent native-button list below
          supplies keyboard, screen-reader and large touch targets for all areas. */}
      <div className={styles.canvas} data-selected={selectedId ?? ""} role="presentation" onClick={(event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const id = Number(target.closest("[data-district]")?.getAttribute("data-district"));
        if (districts.some((district) => district.id === id)) setSelectedId(id);
      }}>{children}</div>
      <div className={styles.selection} role="status" aria-live="polite" aria-atomic="true">
        <p className={styles.selectionTitle}>{selected ? `${selected.roman} · ${selected.name}` : t.home.districtMap.choose}</p>
        <p>{selected ? t.home.districtMap.searchPending : t.home.districtMap.legendHint}</p>
      </div>
      <ul className={styles.legend} aria-label={t.home.districtMap.listLabel}>
        {districts.map((district) => (
          <li key={district.id}>
            <button type="button" aria-pressed={selectedId === district.id} onClick={() => setSelectedId(district.id)} style={{ "--district-hue": district.hue } as CSSProperties}>
              <span className={styles.swatch} aria-hidden="true">{district.roman}</span>
              <span>{district.name}</span>
              <span className={styles.check} aria-hidden="true">{selectedId === district.id ? "✓" : ""}</span>
            </button>
          </li>
        ))}
      </ul>
      <Link className={styles.all} href="/wynajem/krakow">{t.home.areas.all}<span aria-hidden="true"> ↗</span></Link>
      <p className={styles.source}><Link href="/zrodla/mapa-krakowa">{t.home.districtMap.source}</Link></p>
    </section>
  );
}
