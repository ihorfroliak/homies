"use client";

import { useLinkStatus } from "next/link";

import styles from "./results.module.css";

/**
 * A pending mark inside a link while its client navigation loads. A route-level
 * loading.tsx is not an option here: streaming a shell would turn the page's
 * 404s into 200s. The CSS delays the mark so fast navigations never flash it.
 */
export function LinkPending() {
  const { pending } = useLinkStatus();
  return pending ? <span className={styles.pending} data-link-pending aria-hidden="true" /> : null;
}
