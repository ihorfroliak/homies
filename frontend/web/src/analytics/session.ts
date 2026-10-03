/**
 * Analytics session id (EVENTS-v1 §3): in memory only; rotates after 30 min
 * idle, at local midnight (Europe/Warsaw), and on a new non-direct touch.
 */
export const IDLE_MS = 30 * 60 * 1000;

const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Warsaw", year: "numeric", month: "2-digit", day: "2-digit" });

export interface AnalyticsSession {
  /** The current id, rotating first when a rule says so. `isNew` marks a fresh session. */
  touch(now: number, newNonDirectTouch?: boolean): { id: string; isNew: boolean };
  rotate(): void;
}

export function createSession(newId: () => string = () => crypto.randomUUID()): AnalyticsSession {
  let id: string | undefined;
  let lastSeen = 0;
  let day = "";
  return {
    touch(now, newNonDirectTouch = false) {
      const today = dayKey.format(now);
      const expired = id === undefined || now - lastSeen > IDLE_MS || today !== day || newNonDirectTouch;
      if (expired) id = newId();
      lastSeen = now;
      day = today;
      return { id: id as string, isNew: expired };
    },
    rotate() {
      id = undefined;
    },
  };
}
