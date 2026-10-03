import { pl, type Messages, type PluralForms } from "./pl";

/**
 * i18n without a framework (FE-001 decision): typed catalogues + Intl. Locale
 * is fixed to pl-PL for launch; the shape allows en/uk catalogues later
 * without touching call sites. All dates render in Europe/Warsaw (viewing copy
 * must always show date + time in the market's zone).
 */
export const LOCALE = "pl-PL";
export const TIME_ZONE = "Europe/Warsaw";
export const CURRENCY = "PLN";

const catalogues: Record<string, Messages> = { "pl-PL": pl };

export function messages(locale: string = LOCALE): Messages {
  return catalogues[locale] ?? pl;
}

export const t = messages();

const pluralRules = new Intl.PluralRules(LOCALE);

export function plural(forms: PluralForms, n: number): string {
  const category = pluralRules.select(n) as keyof PluralForms;
  const template = forms[category] ?? forms.other;
  return template.replace("{n}", formatInteger(n));
}

// pl-PL omits grouping for 4-digit numbers by default ("3450"); listings always
// group ("3 450") so prices scan the same at every size (DESIGN-001 finding).
const integerFormat = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0, useGrouping: "always" });
const moneyFormat = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: CURRENCY,
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
  useGrouping: "always",
});

export function formatInteger(n: number): string {
  return integerFormat.format(n);
}

/**
 * Money arrives in integer minor units (grosze). Whole amounts show no
 * decimals ("3 450 zł"); fractional amounts keep two ("3 450,50 zł").
 */
export function formatMoney(minor: number): string {
  if (!Number.isInteger(minor)) throw new TypeError("money must be integer minor units");
  const major = minor / 100;
  return Number.isInteger(major)
    ? moneyFormat.format(major)
    : new Intl.NumberFormat(LOCALE, { style: "currency", currency: CURRENCY, minimumFractionDigits: 2, useGrouping: "always" }).format(major);
}

const dateFormat = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, day: "numeric", month: "short", year: "numeric" });
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** A calendar date from the API ("2026-11-01") — no time zone shift. */
export function formatCalendarDate(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) throw new RangeError(`not a calendar date: ${isoDate}`);
  // Noon UTC is the same calendar day in Europe/Warsaw all year.
  return dateFormat.format(new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12)));
}

/** An instant from the API, shown in Europe/Warsaw with date and time. */
export function formatInstant(iso: string): string {
  return dateTimeFormat.format(new Date(iso));
}
