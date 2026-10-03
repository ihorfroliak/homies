/**
 * Experiment assignment seam (docs/growth/EXPERIMENTS-v1.md §2). Sticky and
 * deterministic: bucket = SHA-256(salt ‖ key ‖ unit_id) mod 10 000. No
 * experiment is registered in PROGRAM-001; the registry is the seam.
 *
 * Anonymous units are assigned only with analytics consent; without it they
 * always get control and are marked excluded (never analysed).
 */
export interface Variant {
  name: string;
  /** Share of the 10 000 buckets; the weights of one experiment sum to 10 000. */
  weight: number;
}

export interface Experiment {
  key: string;
  version: number;
  salt: string;
  control: string;
  variants: readonly Variant[];
  active: boolean;
}

export interface Assignment {
  experiment_key: string;
  version: number;
  variant: string;
  excluded: boolean;
}

export const REGISTRY: readonly Experiment[] = [];

export const SEPARATOR = "‖"; // ‖ — cannot appear in keys or ids

export async function bucketOf(salt: string, key: string, unitId: string): Promise<number> {
  const data = new TextEncoder().encode(`${salt}${SEPARATOR}${key}${SEPARATOR}${unitId}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", data));
  // First 6 bytes as an integer (48 bits fit exactly in a double).
  let value = 0;
  for (let i = 0; i < 6; i++) value = value * 256 + (digest[i] ?? 0);
  return value % 10_000;
}

export function validateExperiment(e: Experiment): string | undefined {
  const total = e.variants.reduce((s, v) => s + v.weight, 0);
  if (total !== 10_000) return `${e.key}: weights sum to ${total}, expected 10000`;
  if (!e.variants.some((v) => v.name === e.control)) return `${e.key}: control ${e.control} is not a variant`;
  if (e.variants.some((v) => !Number.isInteger(v.weight) || v.weight < 0)) return `${e.key}: weights must be non-negative integers`;
  return undefined;
}

export async function assign(e: Experiment, unitId: string | undefined, consented: boolean): Promise<Assignment> {
  const base = { experiment_key: e.key, version: e.version };
  if (!e.active || !unitId || !consented) return { ...base, variant: e.control, excluded: true };
  const bucket = await bucketOf(e.salt, e.key, unitId);
  let edge = 0;
  for (const v of e.variants) {
    edge += v.weight;
    if (bucket < edge) return { ...base, variant: v.name, excluded: false };
  }
  return { ...base, variant: e.control, excluded: true };
}
