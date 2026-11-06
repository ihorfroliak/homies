"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";

import { t } from "@/i18n";
import { originFor, safeReturnPath } from "@/search/last-results";

const noSubscription = () => () => undefined;

/**
 * Back to where this listing was opened from, filters and view included, and named
 * for what it is. Without such an origin (a direct link, another tab, no JavaScript,
 * no storage) it offers the listing's city under a label that claims no earlier search.
 */
export function BackToResults({ listingId, fallback, fallbackLabel, className }: { listingId: string; fallback: string; fallbackLabel: string; className?: string }) {
  const path = useSyncExternalStore(noSubscription, () => originFor(listingId)?.path, () => undefined);
  const origin = safeReturnPath(path);
  const label = !origin ? fallbackLabel : origin === "/zapisane" ? t.detail.backSaved : t.detail.back;
  return (
    <Link className={className} href={origin ?? fallback}>
      ← {label}
    </Link>
  );
}
