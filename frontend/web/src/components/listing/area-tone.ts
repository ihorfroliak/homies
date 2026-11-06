/**
 * Identity colours of the Kraków areas in the 001C design source. A colour marks
 * which place this is and says nothing about its quality, safety or price. An area
 * without a designed colour gets none: the caller keeps its neutral surface rather
 * than an invented hue. Keyed by the search neighbourhood's slug, not by district.
 */
const AREA_TONES: Readonly<Record<string, string>> = {
  zablocie: "#5B4A8B",
  podgorze: "#2F6B4F",
  kazimierz: "#9A5418",
  grzegorzki: "#8C2F39",
  krowodrza: "#1F5F7A",
  // Not in the 001C atlas: its official-district hue at the 001C solid lightness.
  "stare-miasto": "oklch(0.46 0.085 60)",
};

export function areaTone(slug: string | null | undefined): string | undefined {
  return slug ? AREA_TONES[slug] : undefined;
}
