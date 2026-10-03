/**
 * Consent state seam (PRIVACY-CONSENT-v1 §1). Every non-essential category
 * defaults to OFF. There is no banner yet: one is shown only once a
 * non-essential category actually does something, and the server-side consent
 * evidence record is legal-gated (G-12). Until then the state stays in memory.
 */
export const CONSENT_POLICY_VERSION = "draft-0";

export type ConsentCategory = "FUNCTIONAL" | "ANALYTICS_FIRST_PARTY" | "MARKETING_ATTRIBUTION";

export interface ConsentState {
  policyVersion: string;
  granted: ReadonlySet<ConsentCategory>;
}

export interface ConsentStore {
  get(): ConsentState;
  has(category: ConsentCategory): boolean;
  set(granted: Iterable<ConsentCategory>): void;
  subscribe(listener: (state: ConsentState) => void): () => void;
}

export function createConsentStore(initial: Iterable<ConsentCategory> = []): ConsentStore {
  let state: ConsentState = { policyVersion: CONSENT_POLICY_VERSION, granted: new Set(initial) };
  const listeners = new Set<(s: ConsentState) => void>();
  return {
    get: () => state,
    has: (category) => state.granted.has(category),
    set(granted) {
      state = { policyVersion: CONSENT_POLICY_VERSION, granted: new Set(granted) };
      for (const l of listeners) l(state);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
