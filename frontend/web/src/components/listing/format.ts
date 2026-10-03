import type { components } from "@/api/schema";
import { fmt, formatCalendarDate, formatMoney, t } from "@/i18n";

type Classified = components["schemas"]["ClassifiedOut"];

/**
 * Monthly total as the card shows it (DESIGN-001 §5.2): "od" when utilities are
 * not stated (the total is a lower bound), "ok." when they are an estimate,
 * plain when included. Nothing is invented for missing costs.
 */
export function monthlyLabel(l: Pick<Classified, "monthly_total_estimate" | "utilities_basis">): string {
  const amount = formatMoney(l.monthly_total_estimate);
  const value = l.utilities_basis === "NOT_STATED" ? fmt(t.card.from, { amount }) : l.utilities_basis === "ESTIMATED" ? fmt(t.card.approx, { amount }) : amount;
  return fmt(t.card.monthly, { amount: value });
}

export function moveInLabel(l: Pick<Classified, "move_in" | "available_from">): string {
  if (l.move_in === "NOW") return t.card.moveInNow;
  if (l.move_in === "FROM_DATE" && l.available_from) return fmt(t.card.moveInFrom, { date: formatCalendarDate(l.available_from) });
  return t.card.moveInUnknown;
}

export function freshnessLabel(l: Pick<Classified, "freshness" | "confirmed_on">): string | undefined {
  if (!l.freshness || l.freshness === "STALE" || !l.confirmed_on) return undefined;
  return fmt(t.freshness[l.freshness], { date: formatCalendarDate(l.confirmed_on) });
}

/** The cover: `is_cover`, else the first public photo. */
export function coverOf(l: Pick<Classified, "media">): Classified["media"][number] | undefined {
  return l.media.find((m) => m.is_cover) ?? l.media[0];
}

export function placeLabel(l: Pick<Classified, "city" | "district">): string {
  return l.district ? `${l.district}, ${l.city}` : l.city;
}

export function factsLine(l: Pick<Classified, "facts" | "space_type">): string[] {
  const out: string[] = [];
  if (l.space_type === "ROOM") out.push(t.card.room);
  const f = l.facts;
  if (f?.rooms) out.push(fmt(t.card.rooms, { n: f.rooms }));
  const area = l.space_type === "ROOM" ? f?.space_area_m2 : f?.area_m2;
  if (area) out.push(fmt(t.card.area, { n: Math.round(area) }));
  return out;
}
