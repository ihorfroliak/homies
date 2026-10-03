import type { AnalyticsEnvelope } from "./types";

/**
 * Where accepted events go. Only first-party, in-process sinks exist (G-12):
 * noop (default), memory (tests, local inspection) and console (development).
 * A first-party ingestion sink is a later, privacy/legal-gated step.
 */
export interface AnalyticsSink {
  send(event: AnalyticsEnvelope): void;
}

export const noopSink: AnalyticsSink = { send() {} };

export function memorySink(limit = 500): AnalyticsSink & { events: AnalyticsEnvelope[] } {
  const events: AnalyticsEnvelope[] = [];
  return {
    events,
    send(event) {
      events.push(event);
      if (events.length > limit) events.shift();
    },
  };
}

export const consoleSink: AnalyticsSink = {
  send(event) {
    console.info("[analytics]", event.event_name, event);
  },
};
