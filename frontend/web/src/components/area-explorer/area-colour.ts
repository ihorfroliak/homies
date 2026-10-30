/**
 * Place-identity hue of an area (1C Dzielnica, D-103). Kraków's districts
 * keep the hues of the DESIGN-001C "Home Mapa" prototype; Kazimierz and
 * Zabłocie take theirs from the 001C Convergence palette (their taxonomy is
 * an open design decision). Any other slug gets a stable hue from the same
 * set. The hue says only "a different place" — never quality, safety,
 * popularity or status — and the name is always shown next to it.
 */
const KNOWN: Record<string, number> = {
  bronowice: 140,
  krowodrza: 230,
  "pradnik-bialy": 30,
  "pradnik-czerwony": 275,
  "nowa-huta": 95,
  zwierzyniec: 345,
  "stare-miasto": 60,
  grzegorzki: 15,
  czyzyny: 180,
  debniki: 205,
  podgorze: 120,
  "podgorze-duchackie": 255,
  "biezanow-prokocim": 305,
  kazimierz: 330, // distinct from Stare Miasto (60); 001C Convergence gave it a hue next to it
  zablocie: 290,
};

/** Every hue the area classes can render (area-explorer.module.css). */
export const AREA_HUES: readonly number[] = [...new Set(Object.values(KNOWN))].sort((a, b) => a - b);

export function areaHue(slug: string): number {
  const known = KNOWN[slug];
  if (known !== undefined) return known;
  let hash = 0x811c9dc5; // 32-bit FNV-1a: stable across pages and builds
  for (let i = 0; i < slug.length; i++) {
    hash ^= slug.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return AREA_HUES[(hash >>> 0) % AREA_HUES.length] ?? 0;
}
