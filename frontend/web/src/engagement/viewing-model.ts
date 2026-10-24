import type { Viewing } from "./api";
export const viewingLabels: Record<string, string> = { REQUESTED: "Prośba wysłana — czeka na potwierdzenie", CONFIRMED: "Oglądanie potwierdzone", DECLINED: "Właściciel nie przyjął tego terminu", CANCELLED: "Oglądanie odwołane", COMPLETED: "Odbyło się", NO_SHOW: "Oznaczone jako nieodbyte" };
export function viewingLabel(viewing: Viewing, now: number) { return viewing.status === "REQUESTED" && Date.parse(viewing.starts_at) <= now ? "Bez odpowiedzi — termin minął" : viewingLabels[viewing.status] ?? viewing.status; }
export function viewingActions(viewing: Viewing, provider: boolean, now: number): string[] {
  const future = Date.parse(viewing.starts_at) > now;
  if (viewing.status === "REQUESTED" && future) return provider ? ["confirm", "decline", "cancel"] : ["cancel"];
  if (viewing.status === "CONFIRMED") return future ? ["cancel"] : provider ? ["COMPLETED", "NO_SHOW"] : [];
  return [];
}
export function viewingTime(instant: string, timezone?: string | null) {
  return `${new Intl.DateTimeFormat("pl-PL", { timeZone: timezone || "UTC", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(instant))} (${timezone || "UTC"})`;
}
export function slotGroups(instants: readonly string[], timezone: string): Map<string, string[]> {
  const formatter = new Intl.DateTimeFormat("pl-PL", { timeZone: timezone, weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const groups = new Map<string, string[]>();
  for (const instant of instants) { const day = formatter.format(new Date(instant)); groups.set(day, [...(groups.get(day) ?? []), instant]); }
  return groups;
}
