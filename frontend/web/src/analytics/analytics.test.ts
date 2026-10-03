import { describe, expect, it } from "vitest";

import { createAnalytics } from ".";
import { unsafeValue, validate } from "./catalogue";
import { createConsentStore } from "./consent";
import { IDLE_MS, createSession } from "./session";
import { memorySink } from "./sinks";

function setup(granted: ("ANALYTICS_FIRST_PARTY" | "MARKETING_ATTRIBUTION")[] = ["ANALYTICS_FIRST_PARTY"]) {
  const sink = memorySink();
  const consent = createConsentStore(granted);
  let clock = Date.UTC(2026, 9, 3, 10, 0, 0);
  let n = 0;
  const refused: string[] = [];
  const analytics = createAnalytics({
    sink,
    consent,
    appVersion: "test",
    now: () => clock,
    newId: () => `00000000-0000-4000-8000-${String(++n).padStart(12, "0")}`,
    onRefused: (r) => refused.push(r),
  });
  return { sink, consent, analytics, refused, advance: (ms: number) => (clock += ms) };
}

describe("consent gate", () => {
  it("emits nothing without analytics consent", () => {
    const { sink, analytics } = setup([]);
    analytics.track("listing_viewed", { listing_id: "abc" }, { route: "/oferta/[id]" });
    expect(sink.events).toHaveLength(0);
  });

  it("stops emitting and drops the anonymous id when consent is withdrawn", () => {
    const { sink, analytics, consent } = setup();
    analytics.track("map_mode_entered", {}, { route: "/wynajem" });
    const firstAnon = sink.events.at(-1)?.anonymous_id;
    consent.set([]);
    analytics.track("map_mode_entered", {}, { route: "/wynajem" });
    const count = sink.events.length;
    consent.set(["ANALYTICS_FIRST_PARTY"]);
    analytics.track("map_mode_entered", {}, { route: "/wynajem" });
    expect(sink.events).toHaveLength(count + 1);
    expect(sink.events.at(-1)?.anonymous_id).not.toBe(firstAnon);
  });
});

describe("envelope", () => {
  it("starts a session, never carries user_id, and records the consent snapshot", () => {
    const { sink, analytics } = setup();
    analytics.track("listing_viewed", { listing_id: "l-1", position: 3 }, { route: "/oferta/[id]" });
    expect(sink.events.map((e) => e.event_name)).toEqual(["session_started", "listing_viewed"]);
    const event = sink.events[1]!;
    expect(event).not.toHaveProperty("user_id");
    expect(event.schema_version).toBe(1);
    expect(event.consent).toEqual({ policy_version: "draft-0", analytics: true, marketing: false });
    expect(event.market).toEqual({ country: "PL", locale: "pl-PL" });
    expect(event.session_id).toBe(sink.events[0]!.session_id);
  });

  it("refuses raw URLs as routes and undeclared or unsafe properties", () => {
    const { sink, analytics, refused } = setup();
    analytics.track("listing_viewed", { listing_id: "l-1" }, { route: "/oferta/123?utm_source=x" });
    analytics.track("listing_viewed", { listing_id: "jan@example.com" }, { route: "/oferta/[id]" });
    // @ts-expect-error — not in the catalogue for this event
    analytics.track("listing_viewed", { email: "x" }, { route: "/oferta/[id]" });
    expect(sink.events).toHaveLength(0);
    expect(refused).toHaveLength(3);
  });
});

describe("catalogue validation", () => {
  it("accepts ids and codes, refuses PII-shaped values", () => {
    expect(unsafeValue("550e8400-e29b-41d4-a716-446655440000")).toBe(false);
    expect(unsafeValue("price_asc")).toBe(false);
    expect(unsafeValue("+48 600 700 800")).toBe(true);
    expect(unsafeValue("600700800")).toBe(true);
    expect(unsafeValue("https://homies.pl/oferta/1")).toBe(true);
    expect(unsafeValue("ładne mieszkanie")).toBe(true);
  });

  it("checks types per property", () => {
    expect(validate("search_performed", { result_count: 4, filter_dimensions: ["rooms", "price"] })).toBeUndefined();
    expect(validate("search_performed", { result_count: "4" })).toMatch(/number/);
    expect(validate("search_performed", { result_count: Number.NaN })).toMatch(/number/);
    expect(validate("nope", {})).toMatch(/unknown/);
  });
});

describe("session rotation", () => {
  it("rotates after 30 minutes idle, at Warsaw midnight, and on a new non-direct touch", () => {
    const ids = ["s1", "s2", "s3", "s4", "s5"];
    const session = createSession(() => ids.shift() as string);
    const t0 = Date.UTC(2026, 9, 3, 20, 0, 0); // 22:00 Warsaw (UTC+2)
    expect(session.touch(t0)).toEqual({ id: "s1", isNew: true });
    expect(session.touch(t0 + IDLE_MS - 1)).toEqual({ id: "s1", isNew: false });
    expect(session.touch(t0 + IDLE_MS - 1 + IDLE_MS + 1).id).toBe("s2");
    const nearMidnight = Date.UTC(2026, 9, 3, 21, 55, 0); // 23:55 Warsaw
    expect(session.touch(nearMidnight).id).toBe("s3"); // idle since 21:00 UTC
    expect(session.touch(nearMidnight + 10 * 60 * 1000).id).toBe("s4"); // 00:05 next day
    expect(session.touch(nearMidnight + 11 * 60 * 1000, true).id).toBe("s5");
  });

  it("resetIdentity rotates the session (shared devices)", () => {
    const { sink, analytics } = setup();
    analytics.track("map_mode_entered", {}, { route: "/wynajem" });
    const before = sink.events.at(-1)!;
    analytics.resetIdentity();
    analytics.track("map_mode_entered", {}, { route: "/wynajem" });
    const after = sink.events.at(-1)!;
    expect(after.session_id).not.toBe(before.session_id);
    expect(after.anonymous_id).not.toBe(before.anonymous_id);
  });
});

describe("sinks", () => {
  it("keeps the memory sink bounded", () => {
    const sink = memorySink(2);
    for (let i = 0; i < 3; i++) sink.send({ event_name: String(i) } as never);
    expect(sink.events.map((e) => e.event_name)).toEqual(["1", "2"]);
  });
});
