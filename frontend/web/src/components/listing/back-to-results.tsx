"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";

import { t } from "@/i18n";
import { readResults } from "@/search/last-results";

const noSubscription = () => () => undefined;

/**
 * Back to the results this tab last showed, filters and view included. The server
 * renders the listing's city, which also stays the target without JavaScript,
 * without storage, or when the listing was opened directly.
 */
export function BackToResults({ fallback, className }: { fallback: string; className?: string }) {
  const remembered = useSyncExternalStore(noSubscription, readResults, () => undefined);
  return (
    <Link className={className} href={remembered ?? fallback}>
      ← {t.detail.back}
    </Link>
  );
}
