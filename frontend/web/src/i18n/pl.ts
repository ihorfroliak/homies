/**
 * Polish catalogue (launch locale, G-13). Keys are stable; EN/UK catalogues
 * later implement the same `Messages` shape. Copy rules: DESIGN-001 §7 (calm,
 * second person singular, no exclamation marks in errors, "czynsz" never
 * alone, freshness never "zweryfikowana"). Plural entries follow
 * Intl.PluralRules("pl") categories: one / few / many / other.
 */
export const pl = {
  meta: {
    siteName: "Homies",
    defaultTitle: "Homies — mieszkania na wynajem z pełnym kosztem miesięcznym",
    defaultDescription: "Oferty wynajmu mieszkań z pełnym kosztem miesięcznym i kosztem na start, potwierdzane jako aktualne.",
  },
  a11y: {
    skipToContent: "Przejdź do treści",
    mainNavigation: "Nawigacja główna",
    footerNavigation: "Stopka",
    loading: "Ładowanie…",
  },
  nav: {
    search: "Szukaj",
    saved: "Zapisane",
    messages: "Wiadomości",
    viewings: "Oglądania",
    account: "Konto",
    addListing: "Dodaj ofertę",
    help: "Pomoc",
    signIn: "Zaloguj się",
    signOut: "Wyloguj się",
  },
  home: {
    heading: "Mieszkania na wynajem z pełnym kosztem miesięcznym",
    lead: "Widzisz, ile naprawdę zapłacisz co miesiąc i na start — zanim napiszesz do właściciela.",
    pillars: {
      fullCost: "Pełny koszt miesięczny i na start",
      fresh: "Oferty potwierdzane jako aktualne",
      // LD-3: legal wording review pending.
      free: "Bez opłat dla szukających",
    },
  },
  errors: {
    notFoundTitle: "Nie znaleźliśmy tej strony",
    notFoundBody: "Adres mógł się zmienić albo oferta nie jest już publiczna.",
    notFoundAction: "Przejdź na stronę główną",
    genericTitle: "Coś poszło nie tak",
    genericBody: "Spróbuj ponownie za chwilę. Jeśli problem się powtórzy, napisz do nas i podaj kod zgłoszenia.",
    requestCode: "Kod zgłoszenia",
    retry: "Spróbuj ponownie",
    network: "Brak połączenia. Sprawdź internet i spróbuj ponownie.",
    timeout: "Serwer odpowiada zbyt długo. Spróbuj ponownie.",
    rateLimited: "Za dużo zapytań w krótkim czasie. Spróbujemy ponownie za chwilę.",
    unavailable: "Serwis jest chwilowo niedostępny. Spróbuj ponownie za chwilę.",
    outcomeUnknown: "Nie wiemy, czy operacja się udała. Sprawdź jej stan, zanim spróbujesz ponownie.",
    unauthorized: "Zaloguj się, aby kontynuować.",
    forbidden: "Nie masz dostępu do tej operacji.",
    validation: "Sprawdź wprowadzone dane.",
    conflict: "Dane zmieniły się w międzyczasie. Odśwież i spróbuj ponownie.",
  },
  units: {
    perMonth: "/ mies.",
  },
  plural: {
    listings: { one: "{n} oferta", few: "{n} oferty", many: "{n} ofert", other: "{n} oferty" },
    rooms: { one: "{n} pokój", few: "{n} pokoje", many: "{n} pokoi", other: "{n} pokoju" },
    months: { one: "{n} miesiąc", few: "{n} miesiące", many: "{n} miesięcy", other: "{n} miesiąca" },
  },
} as const;

type Widen<T> = T extends string ? string : { [K in keyof T]: Widen<T[K]> };
export type Messages = Widen<typeof pl>;
export type PluralForms = Messages["plural"][keyof Messages["plural"]];
