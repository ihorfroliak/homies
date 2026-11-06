import { describe, expect, it } from "vitest";

import { groupOverlaps, type MarkerBox } from "./map-groups";

const box = (key: string, x: number, y: number, weight = 1): MarkerBox => ({ key, x, y, w: 80, h: 28, weight });

describe("groupOverlaps", () => {
  it("leaves separate markers alone", () => {
    expect(groupOverlaps([box("a", 0, 0), box("b", 200, 0), box("c", 0, 100)])).toEqual([
      { representative: "a", members: ["a"] },
      { representative: "b", members: ["b"] },
      { representative: "c", members: ["c"] },
    ]);
  });

  it("groups touching rectangles and accounts for every marker exactly once", () => {
    const groups = groupOverlaps([box("a", 0, 0), box("b", 60, 10), box("c", 400, 0)]);
    expect(groups).toHaveLength(2);
    expect(groups.flatMap((g) => g.members).sort()).toEqual(["a", "b", "c"]);
    expect(groups.find((g) => g.members.length === 2)?.members.sort()).toEqual(["a", "b"]);
  });

  it("is transitive: a chain becomes one group", () => {
    expect(groupOverlaps([box("a", 0, 0), box("b", 70, 0), box("c", 140, 0)])).toHaveLength(1);
  });

  it("does not group markers that only share a column or a row", () => {
    expect(groupOverlaps([box("a", 0, 0), box("b", 0, 40)])).toHaveLength(2);
    expect(groupOverlaps([box("a", 0, 0), box("b", 90, 0)])).toHaveLength(2);
  });

  it("represents a group by its heaviest member, stably", () => {
    expect(groupOverlaps([box("a", 0, 0, 1), box("b", 10, 0, 4)])[0]?.representative).toBe("b");
    const tied = [box("b", 0, 0, 2), box("a", 10, 0, 2)];
    expect(groupOverlaps(tied)[0]?.representative).toBe("a");
    expect(groupOverlaps([...tied].reverse())[0]?.representative).toBe("a");
  });

  it("handles an empty map", () => {
    expect(groupOverlaps([])).toEqual([]);
  });
});
