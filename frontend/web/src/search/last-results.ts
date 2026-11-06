/** The results page this tab last showed, so the listing's back link keeps its filters and view. */
const KEY = "homies.search.last-results";
const MAX_LENGTH = 2048;

/** Storage is untrusted: only a same-origin results path is ever used as a link. */
export function safeResultsPath(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length > MAX_LENGTH) return undefined;
  if (!/^\/wynajem(?:[/?]|$)/.test(value) || value.includes("//") || value.includes("\\")) return undefined;
  return value;
}

export function rememberResults(path: string): void {
  try {
    if (safeResultsPath(path)) sessionStorage.setItem(KEY, path);
  } catch {
    /* Without storage the link falls back to the listing's city. */
  }
}

export function readResults(): string | undefined {
  try {
    return safeResultsPath(sessionStorage.getItem(KEY));
  } catch {
    return undefined;
  }
}
