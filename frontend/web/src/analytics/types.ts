/** Client event envelope (EVENTS-v1 §3). `user_id` is never part of it: the server derives identity. */
export interface AnalyticsEnvelope {
  event_id: string;
  event_name: string;
  schema_version: number;
  occurred_at: string;
  session_id: string;
  anonymous_id?: string;
  platform: { name: "web"; version: string };
  /** Route template ("/oferta/[id]"), never a raw URL or query string. */
  route: string;
  market: { country: string; locale: string; cell_id?: string };
  attribution_ref?: string;
  experiments: { experiment_key: string; version: number; variant: string }[];
  consent: { policy_version: string; analytics: boolean; marketing: boolean };
  props: Record<string, unknown>;
}
