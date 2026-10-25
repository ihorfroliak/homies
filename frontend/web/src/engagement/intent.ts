export const INTENT_KEY = "homies.engagement.intent";
export const INTENT_TTL = 30 * 60 * 1000;
export const ACTIONS = ["save", "message", "viewing", "reveal", "save_search", "report", "account"] as const;
export type Action = typeof ACTIONS[number];
export interface Intent { action: Action; listing_id?: string; starts_at?: string; search_query?: string; message_id?: string; initiator_id: string; created_at: number }
const id = /^[A-Za-z0-9_-]{1,128}$/;
const queryKeys = new Set(["country_code", "locality_id", "geo_area_id", "min_monthly_total", "max_monthly_total", "min_rent", "max_rent", "max_move_in_total", "min_rooms", "min_area_m2", "furnished", "parking", "pets_allowed", "has_elevator", "available_by", "max_term_months", "bbox", "sort"]);
/** Reconstruct approved fields only: storage is untrusted and never holds drafts. */
export function safeIntent(value: unknown, now = Date.now()): Intent | undefined {
  if (!value || typeof value !== "object") return;
  const v = value as Record<string, unknown>;
  if (!ACTIONS.includes(v.action as Action) || typeof v.created_at !== "number" || now - v.created_at >= INTENT_TTL || v.created_at > now || typeof v.initiator_id !== "string" || !id.test(v.initiator_id)) return;
  const out: Intent = { action: v.action as Action, initiator_id: v.initiator_id, created_at: v.created_at };
  for (const key of ["listing_id", "message_id"] as const) {
    if (v[key] !== undefined) { if (typeof v[key] !== "string" || !id.test(v[key])) return; out[key] = v[key]; }
  }
  if (v.starts_at !== undefined) { if (typeof v.starts_at !== "string" || !/^\d{4}-\d{2}-\d{2}T[\d:.+-]+Z?$/.test(v.starts_at) || !Number.isFinite(Date.parse(v.starts_at))) return; out.starts_at = v.starts_at; }
  if (v.search_query !== undefined) {
    if (typeof v.search_query !== "string" || v.search_query.length > 16384) return;
    const q = new URLSearchParams(v.search_query);
    for (const [key, val] of q) if (!queryKeys.has(key) || !/^[A-Za-z0-9.,_+-]{1,128}$/.test(val)) return;
    out.search_query = q.toString();
  }
  return out;
}
export function readIntent(): Intent | undefined { try { return safeIntent(JSON.parse(sessionStorage.getItem(INTENT_KEY) ?? "null")); } catch { return; } }
export function writeIntent(intent?: Intent): void { try { const safe = safeIntent(intent); if (safe) sessionStorage.setItem(INTENT_KEY, JSON.stringify(safe)); else sessionStorage.removeItem(INTENT_KEY); } catch { /* Memory still works when storage is disabled. */ } }
