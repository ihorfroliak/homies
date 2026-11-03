import type { CSSProperties } from "react";

import geometry from "@/geography/krakow-districts.json";
import { t } from "@/i18n";

import { DistrictExplorer } from "./home-district-map-client";
import styles from "./home-district-map.module.css";

/** Geometry stays in the server-rendered SVG, not in the interactive JS bundle. */
export function HomeDistrictMap() {
  return (
    <DistrictExplorer districts={geometry.districts.map(({ id, roman, name, hue }) => ({ id, roman, name, hue }))}>
      <svg viewBox={geometry.viewBox} className={styles.map} aria-hidden="true" focusable="false">
        {geometry.districts.map((district) => (
          <g key={district.id} style={{ "--district-hue": district.hue } as CSSProperties}>
            <path data-district={district.id} d={district.path} fillRule="evenodd" className={styles.district}>
              <title>{district.roman} · {district.name}</title>
            </path>
            <text x={district.label[0]} y={district.label[1]} className={styles.number} dominantBaseline="central" textAnchor="middle">{district.roman}</text>
          </g>
        ))}
        <text x="28" y="30" className={styles.north}>{t.home.districtMap.north}</text>
      </svg>
    </DistrictExplorer>
  );
}
