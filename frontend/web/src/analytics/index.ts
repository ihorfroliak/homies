import { CATALOGUE, validate, type EventName, type EventProps } from "./catalogue";
import type { ConsentStore } from "./consent";
import { createSession, type AnalyticsSession } from "./session";
import { noopSink, type AnalyticsSink } from "./sinks";
import type { AnalyticsEnvelope } from "./types";

/**
 * The only door to analytics (PRIVACY-CONSENT-v1 §2): components call
 * `analytics.track(...)`, never a vendor. Gate: without ANALYTICS_FIRST_PARTY
 * consent nothing is emitted at all (G-12 keeps ingestion legal-gated), so the
 * default deployment produces no analytics data. Invalid payloads are dropped
 * and reported to `onRefused` (tests and development make them loud).
 */
export interface AnalyticsOptions {
  sink?: AnalyticsSink;
  consent: ConsentStore;
  appVersion: string;
  market?: { country: string; locale: string; cell_id?: string };
  now?: () => number;
  newId?: () => string;
  session?: AnalyticsSession;
  onRefused?: (reason: string) => void;
}

export interface Analytics {
  track<N extends EventName>(name: N, props: EventProps<N>, context: { route: string }): void;
  setExperiments(assigned: AnalyticsEnvelope["experiments"]): void;
  setAttributionRef(ref: string | undefined): void;
  /** Shared devices: logout or consent withdrawal starts a fresh identity. */
  resetIdentity(): void;
}

const ROUTE_TEMPLATE = /^\/[A-Za-z0-9_\-/[\]]*$/;

export function createAnalytics(options: AnalyticsOptions): Analytics {
  const sink = options.sink ?? noopSink;
  const now = options.now ?? Date.now;
  const newId = options.newId ?? (() => crypto.randomUUID());
  const session = options.session ?? createSession(newId);
  const market = options.market ?? { country: "PL", locale: "pl-PL" };
  let anonymousId: string | undefined;
  let experiments: AnalyticsEnvelope["experiments"] = [];
  let attributionRef: string | undefined;
  const refuse = options.onRefused ?? (() => {});

  options.consent.subscribe((state) => {
    if (!state.granted.has("ANALYTICS_FIRST_PARTY")) {
      anonymousId = undefined;
      attributionRef = undefined;
    }
  });

  function emit(name: string, version: number, props: Record<string, unknown>, route: string, sessionId: string): void {
    const consent = options.consent.get();
    anonymousId ??= newId();
    sink.send({
      event_id: newId(),
      event_name: name,
      schema_version: version,
      occurred_at: new Date(now()).toISOString(),
      session_id: sessionId,
      anonymous_id: anonymousId,
      platform: { name: "web", version: options.appVersion },
      route,
      market,
      attribution_ref: consent.granted.has("MARKETING_ATTRIBUTION") || consent.granted.has("ANALYTICS_FIRST_PARTY") ? attributionRef : undefined,
      experiments,
      consent: {
        policy_version: consent.policyVersion,
        analytics: consent.granted.has("ANALYTICS_FIRST_PARTY"),
        marketing: consent.granted.has("MARKETING_ATTRIBUTION"),
      },
      props,
    });
  }

  return {
    track(name, props, context) {
      if (!options.consent.has("ANALYTICS_FIRST_PARTY")) return;
      if (!ROUTE_TEMPLATE.test(context.route)) return refuse(`route must be a template, got ${context.route}`);
      const payload = props as Record<string, unknown>;
      const reason = validate(name, payload);
      if (reason) return refuse(reason);
      const { id, isNew } = session.touch(now());
      if (isNew && name !== "session_started") emit("session_started", 1, {}, context.route, id);
      const version = CATALOGUE[name].version;
      emit(name, version, payload, context.route, id);
    },
    setExperiments(assigned) {
      experiments = assigned;
    },
    setAttributionRef(ref) {
      attributionRef = ref;
    },
    resetIdentity() {
      anonymousId = undefined;
      attributionRef = undefined;
      session.rotate();
    },
  };
}


