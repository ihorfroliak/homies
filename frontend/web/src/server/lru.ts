/** A small bounded TTL cache (insertion-ordered Map; a hit is re-inserted, so eviction drops the least recently used). */
export class TtlLru<V> {
  private readonly entries = new Map<string, { at: number; value: V }>();

  constructor(
    private readonly max: number,
    private readonly ttlMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  get(key: string): { value: V } | undefined {
    const hit = this.entries.get(key);
    if (!hit) return undefined;
    this.entries.delete(key);
    if (this.now() - hit.at >= this.ttlMs) return undefined;
    this.entries.set(key, hit);
    return { value: hit.value };
  }

  set(key: string, value: V): void {
    this.entries.delete(key);
    this.entries.set(key, { at: this.now(), value });
    while (this.entries.size > this.max) {
      const oldest = this.entries.keys().next().value;
      if (oldest === undefined) break;
      this.entries.delete(oldest);
    }
  }

  get size(): number {
    return this.entries.size;
  }
}
