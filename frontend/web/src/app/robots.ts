import type { MetadataRoute } from "next";

/**
 * robots.txt allows crawling (so crawlers can SEE the noindex header/meta) and
 * keeps private and API surfaces out. Indexing itself is controlled by the
 * INDEXING_ENABLED kill switch in proxy.ts and page metadata (DESIGN-001 §8).
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/bff/", "/konto", "/panel", "/zapisane", "/wiadomosci", "/ogladania"] }],
  };
}
