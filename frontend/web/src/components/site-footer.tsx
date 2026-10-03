import { t } from "@/i18n";

import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className="container">
        <nav aria-label={t.a11y.footerNavigation}>
          <p className="small muted">
            © {new Date().getFullYear()} {t.meta.siteName}
          </p>
        </nav>
      </div>
    </footer>
  );
}
