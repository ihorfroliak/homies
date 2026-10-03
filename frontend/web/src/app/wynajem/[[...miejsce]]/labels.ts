import { fmt, formatCalendarDate, formatMoney, t } from "@/i18n";
import type { FilterKey, SearchState } from "@/search/codec";

const zl = (v: number) => formatMoney(v * 100);

/** The removable chip text for one active filter. */
export function chipLabel(key: FilterKey, s: SearchState): string {
  switch (key) {
    case "monthlyMin": return fmt(t.chips.monthlyMin, { v: zl(s.monthlyMin ?? 0) });
    case "monthlyMax": return fmt(t.chips.monthlyMax, { v: zl(s.monthlyMax ?? 0) });
    case "rentMin": return fmt(t.chips.rentMin, { v: zl(s.rentMin ?? 0) });
    case "rentMax": return fmt(t.chips.rentMax, { v: zl(s.rentMax ?? 0) });
    case "moveInMax": return fmt(t.chips.moveInMax, { v: zl(s.moveInMax ?? 0) });
    case "roomsMin": return fmt(t.chips.roomsMin, { v: s.roomsMin ?? 0 });
    case "areaMin": return fmt(t.chips.areaMin, { v: s.areaMin ?? 0 });
    case "termMax": return fmt(t.chips.termMax, { v: s.termMax ?? 0 });
    case "availableBy": return fmt(t.chips.availableBy, { v: s.availableBy ? formatCalendarDate(s.availableBy) : "" });
    case "furnished": return `${t.filters.furnished}: ${s.furnished ? t.filters.furnishedValues[s.furnished] : ""}`;
    case "parking": return `${t.filters.parking}: ${s.parking ? t.filters.parkingValues[s.parking] : ""}`;
    case "pets": return t.filters.pets;
    case "elevator": return t.filters.elevator;
    case "bbox": return t.filters.mapArea;
  }
}
