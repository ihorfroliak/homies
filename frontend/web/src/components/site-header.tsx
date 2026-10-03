import Link from "next/link";

import { t } from "@/i18n";

import styles from "./site-header.module.css";

/**
 * Desktop top bar (DESIGN-001 §2). Saved / messages / account entries arrive
 * with the slices that implement them (FE-003+). The bar links only to routes
 * that exist in this build, never to one that is not built.
 */
export function SiteHeader() {
  return (
    <header className={styles.header}>
      <div className={`container ${styles.inner}`}>
        <Link href="/" className={styles.logo} aria-label={`${t.meta.siteName} — strona główna`}>
          Homies
        </Link>
        <nav aria-label={t.a11y.mainNavigation}>
          <ul className={styles.links}>
            <li>
              <Link href="/wynajem">{t.nav.search}</Link>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
