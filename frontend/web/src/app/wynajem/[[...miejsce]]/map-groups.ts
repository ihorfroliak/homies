/** A marker's on-screen rectangle: (x, y) is its anchor at the middle of its bottom edge. */
export interface MarkerBox {
  key: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Listings behind the marker; the heaviest one represents a group. */
  weight: number;
}

export interface MarkerGroup {
  representative: string;
  members: string[];
}

function intersect(a: MarkerBox, b: MarkerBox, gap: number): boolean {
  return Math.abs(a.x - b.x) < (a.w + b.w) / 2 + gap && a.y - a.h < b.y + gap && b.y - b.h < a.y + gap;
}

/**
 * Groups markers whose rectangles touch at the current zoom, transitively. This
 * only decides what is drawn: no coordinate changes, and the group is drawn at a
 * real member's position. The heaviest member represents it (key breaks ties, so
 * the choice is stable between recomputations).
 */
export function groupOverlaps(boxes: readonly MarkerBox[], gap = 2): MarkerGroup[] {
  const parent = boxes.map((_, i) => i);
  const find = (start: number): number => {
    let i = start;
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]!]!;
      i = parent[i]!;
    }
    return i;
  };
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      if (intersect(boxes[i]!, boxes[j]!, gap)) parent[find(i)] = find(j);
    }
  }
  const byRoot = new Map<number, MarkerBox[]>();
  boxes.forEach((box, i) => {
    const root = find(i);
    byRoot.set(root, [...(byRoot.get(root) ?? []), box]);
  });
  return [...byRoot.values()].map((members) => {
    const ordered = [...members].sort((a, b) => b.weight - a.weight || (a.key < b.key ? -1 : 1));
    return { representative: ordered[0]!.key, members: ordered.map((m) => m.key) };
  });
}
