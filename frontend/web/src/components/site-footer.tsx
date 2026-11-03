import { t } from "@/i18n";
import Link from "next/link";
import { BrandMark } from "./brand-mark";

import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.grid}`}>
        <div>
          <Link href="/" className={styles.brand} aria-label={`${t.meta.siteName} — strona główna`}><BrandMark />Homies</Link>
          <p className={styles.description}>{t.footer.description}</p>
        </div>
        <nav aria-label={t.a11y.footerNavigation} className={styles.navigation}>
          <div><h2>{t.footer.find}</h2><ul>
            <li><Link href="/wynajem/krakow">{t.footer.krakow}</Link></li>
            <li><Link href="/wynajem">{t.footer.allPlaces}</Link></li>
            <li><Link href="/zapisane">{t.nav.saved}</Link></li>
          </ul></div>
          <div><h2>{t.footer.understand}</h2><ul>
            <li><Link href="/#koszty">{t.footer.costs}</Link></li>
            <li><Link href="/zrodla/mapa-krakowa">{t.footer.mapSource}</Link></li>
          </ul></div>
        </nav>
      </div>
      <div className={`container ${styles.bottom}`}><p>© {new Date().getFullYear()} {t.meta.siteName}</p><p>{t.footer.scope}</p></div>
    </footer>
  );
}
