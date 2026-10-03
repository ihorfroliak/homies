import { describe, expect, it } from "vitest";

import { captureTouch, channelOf } from "./attribution";
import { REGISTRY, assign, bucketOf, validateExperiment, type Experiment } from "./experiments";
import { robotsFor } from "./seo";

const HOST = "homies.pl";

describe("attribution", () => {
  it("keeps allowlisted UTM codes and only the presence of a click id", () => {
    const touch = captureTouch("https://homies.pl/wynajem/krakow?utm_source=google&utm_medium=cpc&utm_campaign=krk_launch&gclid=SECRET123", undefined, HOST, "/wynajem/[miasto]");
    expect(touch).toEqual({
      channel_code: "PAID_SEARCH",
      utm_source: "google",
      utm_medium: "cpc",
      utm_campaign: "krk_launch",
      click_id_present: true,
      click_id_platform: "google",
      landing_route_template: "/wynajem/[miasto]",
    });
    expect(JSON.stringify(touch)).not.toContain("SECRET123");
  });

  it("drops free-text or PII-shaped UTM values", () => {
    const touch = captureTouch("https://homies.pl/?utm_source=jan%40example.com&utm_campaign=Hello%20World", undefined, HOST, "/");
    expect(touch?.utm_source).toBeUndefined();
    expect(touch?.utm_campaign).toBeUndefined();
  });

  it("keeps the referrer domain, never its path", () => {
    const touch = captureTouch("https://homies.pl/oferta/1", "https://www.google.com/search?q=mieszkanie+krakow", HOST, "/oferta/[id]");
    expect(touch).toMatchObject({ channel_code: "ORGANIC_SEARCH", referrer_domain: "www.google.com" });
    expect(JSON.stringify(touch)).not.toContain("mieszkanie");
  });

  it("ignores same-site navigation", () => {
    expect(captureTouch("https://homies.pl/oferta/1", "https://homies.pl/wynajem", HOST, "/oferta/[id]")).toBeUndefined();
  });

  it("classifies channels", () => {
    expect(channelOf("email", undefined, undefined, undefined)).toBe("EMAIL");
    expect(channelOf(undefined, undefined, "meta", undefined)).toBe("PAID_SOCIAL");
    expect(channelOf(undefined, undefined, undefined, "forum.example")).toBe("REFERRAL");
    expect(channelOf(undefined, undefined, undefined, undefined)).toBe("DIRECT");
  });
});

describe("experiments", () => {
  const exp: Experiment = { key: "home_hero", version: 1, salt: "s1", control: "control", variants: [{ name: "control", weight: 5000 }, { name: "b", weight: 5000 }], active: true };

  it("has no registered experiment in PROGRAM-001", () => {
    expect(REGISTRY).toHaveLength(0);
  });

  it("assigns deterministically and stickily", async () => {
    const a = await assign(exp, "unit-1", true);
    const b = await assign(exp, "unit-1", true);
    expect(a).toEqual(b);
    expect(a.excluded).toBe(false);
  });

  it("gives control and excludes units without consent or id", async () => {
    expect(await assign(exp, "unit-1", false)).toEqual({ experiment_key: "home_hero", version: 1, variant: "control", excluded: true });
    expect((await assign(exp, undefined, true)).excluded).toBe(true);
    expect((await assign({ ...exp, active: false }, "u", true)).excluded).toBe(true);
  });

  it("spreads buckets roughly evenly", async () => {
    let inB = 0;
    for (let i = 0; i < 2000; i++) if ((await assign(exp, `u${i}`, true)).variant === "b") inB++;
    expect(inB).toBeGreaterThan(900);
    expect(inB).toBeLessThan(1100);
    const bucket = await bucketOf("s", "k", "u");
    expect(bucket).toBeGreaterThanOrEqual(0);
    expect(bucket).toBeLessThan(10_000);
  });

  it("validates weights and control", () => {
    expect(validateExperiment(exp)).toBeUndefined();
    expect(validateExperiment({ ...exp, variants: [{ name: "control", weight: 9000 }] })).toMatch(/sum/);
    expect(validateExperiment({ ...exp, control: "x" })).toMatch(/control/);
  });
});

describe("robots", () => {
  it("indexes nothing while the kill switch is off", () => {
    expect(robotsFor({ kind: "home" }, false)).toEqual({ index: false, follow: false });
    expect(robotsFor({ kind: "listing", public: true }, false).index).toBe(false);
  });

  it("indexes only bare result pages with results when enabled", () => {
    const base = { kind: "results" as const, filtered: false, page: 1, total: 12, mapView: false };
    expect(robotsFor(base, true)).toEqual({ index: true, follow: true });
    expect(robotsFor({ ...base, filtered: true }, true).index).toBe(false);
    expect(robotsFor({ ...base, page: 2 }, true).index).toBe(false);
    expect(robotsFor({ ...base, total: 0 }, true).index).toBe(false);
    expect(robotsFor({ ...base, mapView: true }, true).index).toBe(false);
    expect(robotsFor({ kind: "listing", public: false }, true).index).toBe(false);
    expect(robotsFor({ kind: "private" }, true).index).toBe(false);
  });
});
