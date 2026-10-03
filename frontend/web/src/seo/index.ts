import type { Metadata } from "next";

import { t } from "@/i18n";

/**
 * Indexing rules (DESIGN-001 §8). The kill switch (INDEXING_ENABLED) wins over
 * everything: until the founder enables it, every response carries
 * `X-Robots-Tag: noindex, nofollow` from proxy.ts and every page's robots
 * metadata says noindex. When enabled, only bare city/area result paths with
 * results and public listing pages are indexable.
 */
export type PageKind =
  | { kind: "home" }
  | { kind: "results"; filtered: boolean; page: number; total: number; mapView: boolean }
  | { kind: "listing"; public: boolean }
  | { kind: "private" }
  | { kind: "error" };

export interface RobotsDecision {
  index: boolean;
  follow: boolean;
}

export function robotsFor(page: PageKind, indexingEnabled: boolean): RobotsDecision {
  if (!indexingEnabled) return { index: false, follow: false };
  switch (page.kind) {
    case "home":
      return { index: true, follow: true };
    case "results":
      return { index: !page.filtered && page.page <= 1 && page.total > 0 && !page.mapView, follow: true };
    case "listing":
      return { index: page.public, follow: page.public };
    case "private":
    case "error":
      return { index: false, follow: false };
  }
}

export function indexingEnabled(): boolean {
  return process.env.INDEXING_ENABLED === "1";
}

export function pageMetadata(input: { title?: string; description?: string; canonicalPath?: string; page: PageKind }): Metadata {
  const robots = robotsFor(input.page, indexingEnabled());
  return {
    title: input.title ? `${input.title} | ${t.meta.siteName}` : t.meta.defaultTitle,
    description: input.description ?? t.meta.defaultDescription,
    robots: { index: robots.index, follow: robots.follow },
    ...(input.canonicalPath ? { alternates: { canonical: input.canonicalPath } } : {}),
  };
}
