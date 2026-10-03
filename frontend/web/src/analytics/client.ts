"use client";

import { createAnalytics, type Analytics } from ".";
import { createConsentStore, type ConsentStore } from "./consent";
import { consoleSink, memorySink, noopSink, type AnalyticsSink } from "./sinks";

/**
 * The browser's single analytics instance. Consent starts empty, so nothing is
 * emitted (G-12) until a consent UI exists. NEXT_PUBLIC_ANALYTICS_SINK picks an
 * in-process sink for development (console) or E2E (memory); production keeps
 * noop. NEXT_PUBLIC_E2E_HOOKS=1 (E2E builds only) exposes the consent store and
 * the memory sink on window so tests can prove the gate and the payloads.
 */
let instance: { analytics: Analytics; consent: ConsentStore; sink: AnalyticsSink } | undefined;

function sinkFromEnv(): AnalyticsSink {
  switch (process.env.NEXT_PUBLIC_ANALYTICS_SINK) {
    case "console":
      return consoleSink;
    case "memory":
      return memorySink();
    default:
      return noopSink;
  }
}

export function browserAnalytics() {
  if (!instance) {
    const hooks = process.env.NEXT_PUBLIC_E2E_HOOKS === "1" && typeof window !== "undefined";
    // E2E only: a test may preset consent before the page loads (addInitScript).
    const preset = hooks ? (window as unknown as { __homiesConsentPreset?: unknown }).__homiesConsentPreset : undefined;
    const consent = createConsentStore(Array.isArray(preset) ? (preset as ("ANALYTICS_FIRST_PARTY" | "MARKETING_ATTRIBUTION" | "FUNCTIONAL")[]) : []);
    const sink = sinkFromEnv();
    const analytics = createAnalytics({ sink, consent, appVersion: process.env.NEXT_PUBLIC_APP_VERSION ?? "dev" });
    instance = { analytics, consent, sink };
    if (process.env.NEXT_PUBLIC_E2E_HOOKS === "1" && typeof window !== "undefined") {
      (window as unknown as Record<string, unknown>).__homies = { consent, sink };
    }
  }
  return instance;
}

/** search_id → listing_viewed correlation, in memory only (never in the URL or storage). */
let lastSearch: { searchId: string; listingId: string; position?: number } | undefined;

export function rememberClick(searchId: string, listingId: string, position?: number): void {
  lastSearch = { searchId, listingId, position };
}

export function takeSearchRef(listingId: string): { searchId?: string; position?: number } {
  if (!lastSearch || lastSearch.listingId !== listingId) return {};
  const ref = { searchId: lastSearch.searchId, position: lastSearch.position };
  lastSearch = undefined;
  return ref;
}
