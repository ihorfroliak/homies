/**
 * Closed client-event catalogue (docs/growth/EVENTS-v1.md §3). An event not
 * listed here cannot be tracked; a property not listed for its event is
 * refused. Business facts (publish, contact, viewing) come from the server
 * outbox, never from the client.
 */
type Prop = "string" | "number" | "boolean" | "string[]";

interface EventSpec {
  version: number;
  props: Record<string, Prop>;
}

export const CATALOGUE = {
  session_started: { version: 1, props: {} },
  landing_viewed: { version: 1, props: { channel_code: "string" } },
  attribution_captured: { version: 1, props: { channel_code: "string", utm_source: "string", utm_medium: "string", utm_campaign: "string", click_id_present: "boolean", click_id_platform: "string" } },
  signup_started: { version: 1, props: { intent: "string" } },
  search_performed: {
    version: 1,
    props: {
      search_id: "string",
      filter_dimensions: "string[]",
      locality_id: "string",
      area_id: "string",
      space_type: "string",
      category: "string",
      price_band: "number",
      sort: "string",
      result_count: "number",
      surface: "string",
    },
  },
  search_results_viewed: { version: 1, props: { search_id: "string", page_index: "number", visible_count: "number" } },
  listing_viewed: { version: 1, props: { listing_id: "string", search_id: "string", position: "number" } },
  map_mode_entered: { version: 1, props: { search_id: "string" } },
  experiment_exposed: { version: 1, props: { experiment_key: "string", experiment_version: "number", variant: "string" } },
  consent_updated: { version: 1, props: { policy_version: "string", categories: "string[]" } },
  web_vital: { version: 1, props: { metric: "string", value: "number" } },
} as const satisfies Record<string, EventSpec>;

export type EventName = keyof typeof CATALOGUE;

type PropType<P extends Prop> = P extends "string" ? string : P extends "number" ? number : P extends "boolean" ? boolean : string[];

export type EventProps<N extends EventName> = {
  [K in keyof (typeof CATALOGUE)[N]["props"]]?: PropType<(typeof CATALOGUE)[N]["props"][K] & Prop>;
};

// Values that must never reach analytics (PRIVACY-CONSENT-v1 §2): e-mail,
// phone-like digit runs, URLs, and free text. Identifiers and codes are short.
const EMAIL = /@/;
const PHONE = /(?:\d[\s-]?){7,}/;
const URLISH = /:\/\/|^www\.|[?&=]/i;
const SAFE_STRING = /^[A-Za-z0-9_.:-]{1,64}$/;

export function unsafeValue(value: string): boolean {
  return EMAIL.test(value) || URLISH.test(value) || !SAFE_STRING.test(value) || (PHONE.test(value) && !/^[0-9a-f-]{36}$/i.test(value));
}

/** Returns the reason a payload is refused, or undefined when it is clean. */
export function validate(name: string, props: Record<string, unknown>): string | undefined {
  const spec = (CATALOGUE as Record<string, EventSpec>)[name];
  if (!spec) return `unknown event ${name}`;
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined) continue;
    const type = spec.props[key];
    if (!type) return `property ${key} is not allowed on ${name}`;
    if (type === "string[]") {
      if (!Array.isArray(value) || value.length > 32 || value.some((v) => typeof v !== "string" || unsafeValue(v))) return `property ${key} must be a list of codes`;
    } else if (type === "string") {
      if (typeof value !== "string" || unsafeValue(value)) return `property ${key} must be a code or id`;
    } else if (typeof value !== type || (type === "number" && !Number.isFinite(value))) {
      return `property ${key} must be ${type}`;
    }
  }
  return undefined;
}
