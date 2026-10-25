import { describe, expect, it } from "vitest";
import { slotGroups, viewingActions, viewingLabel, viewingTime } from "./viewing-model";
import type { Viewing } from "./api";
const start = Date.parse("2026-10-25T10:00:00Z");
const viewing = (status: string): Viewing => ({ id: "v", listing_id: "l", status, starts_at: "2026-10-25T10:00:00Z", ends_at: "2026-10-25T10:30:00Z", attendee_count: 1, cancelled_by_homies: false });
describe("viewing lifecycle from API state", () => {
  it.each(["DECLINED", "CANCELLED", "COMPLETED", "NO_SHOW"])("terminal%s has no actions", status => { expect(viewingActions(viewing(status), true, start - 1)).toEqual([]); expect(viewingActions(viewing(status), false, start + 1)).toEqual([]); });
  it("refuses requester and provider cancellation exactly at start", () => { expect(viewingActions(viewing("REQUESTED"), true, start)).toEqual([]); expect(viewingActions(viewing("CONFIRMED"), false, start)).toEqual([]); expect(viewingActions(viewing("CONFIRMED"), true, start)).toEqual(["COMPLETED", "NO_SHOW"]); });
  it("offers only capability-appropriate future transitions", () => { expect(viewingActions(viewing("REQUESTED"), true, start - 1)).toEqual(["confirm", "decline", "cancel"]); expect(viewingActions(viewing("REQUESTED"), false, start - 1)).toEqual(["cancel"]); expect(viewingActions(viewing("CONFIRMED"), true, start - 1)).toEqual(["cancel"]); });
  it("labels passed requested without mutating state and hides cancellation source", () => { const v = viewing("REQUESTED"); expect(viewingLabel(v, start)).toBe("Bez odpowiedzi — termin minął"); expect(v.status).toBe("REQUESTED"); expect(viewingLabel({ ...viewing("CANCELLED"), cancelled_by: "HOMIES" }, start)).toBe("Oglądanie odwołane"); });
});
describe("timezone and returned-instant fidelity", () => {
  it("groups only returned instants in API timezone across midnight", () => { const slots = ["2026-10-25T00:00:00Z", "2026-10-25T23:00:00Z"]; const grouped = slotGroups(slots, "America/New_York"); expect(grouped.size).toBe(2); expect([...grouped.values()].flat()).toEqual(slots); });
  it("renders a non-Polish zone and explicitly marks UTC when no schedule exists", () => { expect(viewingTime("2026-10-25T10:00:00Z", "Asia/Tokyo")).toContain("19:00"); expect(viewingTime("2026-10-25T10:00:00Z")).toContain("10:00 (UTC)"); });
  it("does not invent DST transition slots", () => { const slots = ["2026-03-29T00:30:00Z", "2026-03-29T01:30:00Z"]; expect([...slotGroups(slots, "Europe/Warsaw").values()].flat()).toEqual(slots); expect(viewingTime(slots[1]!, "Europe/Warsaw")).toContain("03:30"); });
});
