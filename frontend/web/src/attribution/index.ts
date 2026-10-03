/**
 * Attribution touch capture (docs/growth/ATTRIBUTION-v1.md §1). Pure: turns a
 * landing URL + referrer into a privacy-safe touch. Raw click ids, full URLs
 * and referrer paths are never kept — only a presence flag and the platform,
 * and the referrer's domain. Persisting the touch beyond the session needs
 * consent; the caller decides where it lives.
 */
export type ChannelCode = "PAID_SEARCH" | "PAID_SOCIAL" | "ORGANIC_SEARCH" | "REFERRAL" | "PARTNER" | "CONCIERGE" | "EMAIL" | "DIRECT";

export interface Touch {
  channel_code: ChannelCode;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  click_id_present: boolean;
  click_id_platform?: string;
  referrer_domain?: string;
  landing_route_template: string;
}

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const;
// Allowlisted shape: lowercase codes only. Anything else (free text, e-mails,
// ids smuggled into a campaign name) is dropped, not stored.
const UTM_VALUE = /^[a-z0-9][a-z0-9_.-]{0,63}$/;

const CLICK_IDS: Record<string, string> = { gclid: "google", gbraid: "google", wbraid: "google", fbclid: "meta", msclkid: "microsoft", ttclid: "tiktok", li_fat_id: "linkedin" };

const SEARCH_ENGINES = /(^|\.)(google|bing|duckduckgo|yahoo|yandex|ecosia|seznam|onet|wp)\.[a-z.]+$/;

const PAID_MEDIUMS = new Set(["cpc", "ppc", "paid", "paid_search", "paidsearch"]);
const PAID_SOCIAL_MEDIUMS = new Set(["paid_social", "paidsocial", "social_paid", "cpm"]);

export function captureTouch(landingUrl: string, referrer: string | undefined, ownHost: string, routeTemplate: string): Touch | undefined {
  let url: URL;
  try {
    url = new URL(landingUrl);
  } catch {
    return undefined;
  }
  const utm: Partial<Record<(typeof UTM_KEYS)[number], string>> = {};
  for (const key of UTM_KEYS) {
    const raw = url.searchParams.get(key)?.trim().toLowerCase();
    if (raw && UTM_VALUE.test(raw)) utm[key] = raw;
  }
  let clickPlatform: string | undefined;
  for (const [param, platform] of Object.entries(CLICK_IDS)) {
    if (url.searchParams.has(param)) {
      clickPlatform = platform;
      break;
    }
  }
  let referrerDomain: string | undefined;
  if (referrer) {
    try {
      const host = new URL(referrer).hostname.toLowerCase();
      if (host && host !== ownHost) referrerDomain = host;
    } catch {
      // unusable referrer: treated as none
    }
  }
  const channel = channelOf(utm.utm_medium, utm.utm_source, clickPlatform, referrerDomain);
  // A same-site navigation with no campaign is not a touch at all.
  if (channel === "DIRECT" && referrer && !referrerDomain) return undefined;
  return {
    channel_code: channel,
    ...utm,
    click_id_present: clickPlatform !== undefined,
    ...(clickPlatform ? { click_id_platform: clickPlatform } : {}),
    ...(referrerDomain ? { referrer_domain: referrerDomain } : {}),
    landing_route_template: routeTemplate,
  };
}

export function channelOf(medium: string | undefined, source: string | undefined, clickPlatform: string | undefined, referrerDomain: string | undefined): ChannelCode {
  if (medium === "email" || medium === "newsletter") return "EMAIL";
  if (medium === "partner") return "PARTNER";
  if (medium === "concierge" || source === "concierge") return "CONCIERGE";
  if (medium && PAID_SOCIAL_MEDIUMS.has(medium)) return "PAID_SOCIAL";
  if (medium && PAID_MEDIUMS.has(medium)) return clickPlatform === "meta" || clickPlatform === "tiktok" ? "PAID_SOCIAL" : "PAID_SEARCH";
  if (clickPlatform === "google" || clickPlatform === "microsoft") return "PAID_SEARCH";
  if (clickPlatform) return "PAID_SOCIAL";
  if (medium === "referral") return "REFERRAL";
  if (referrerDomain) {
    return SEARCH_ENGINES.test(referrerDomain) ? "ORGANIC_SEARCH" : "REFERRAL";
  }
  return "DIRECT";
}

/** Last non-direct rule (ATTRIBUTION-v1 §2): a DIRECT touch never replaces a known channel. */
export function isNonDirect(touch: Touch): boolean {
  return touch.channel_code !== "DIRECT";
}
