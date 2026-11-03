"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { t } from "@/i18n";

import styles from "./site-header.module.css";

/** One set of links/session actions across breakpoints; ordinary site navigation,
 * not an ARIA application menu. Opening authentication keeps its initiator mounted. */
export function SiteNavigation({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!(event.target instanceof Node) || root.current?.contains(event.target)) return;
      // The auth dialog owns focus while open. Do not hide its return target.
      if (document.querySelector('[role="dialog"], dialog[open]')) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  return (
    <div ref={root} className={styles.navigation} data-open={open} onKeyDown={(event) => {
      if (event.key === "Escape" && open) {
        event.stopPropagation();
        setOpen(false);
        trigger.current?.focus();
      }
    }}>
      <button ref={trigger} type="button" className={styles.menuButton} aria-expanded={open} aria-controls="site-navigation" onClick={() => setOpen((previous) => !previous)}>
        {open ? t.nav.closeMenu : t.nav.menu}
      </button>
      <nav id="site-navigation" className={styles.nav} aria-label={t.a11y.mainNavigation} onClick={(event) => {
        if (event.target instanceof Element && event.target.closest("a[href]")) setOpen(false);
      }}>
        <ul className={styles.links}>{children}</ul>
      </nav>
    </div>
  );
}
