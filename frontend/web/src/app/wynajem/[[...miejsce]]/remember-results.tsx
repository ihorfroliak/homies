"use client";

import { useEffect } from "react";

import { rememberResults } from "@/search/last-results";

/** Records the canonical URL of the results on screen for the listing's back link. */
export function RememberResults({ href }: { href: string }) {
  useEffect(() => rememberResults(href), [href]);
  return null;
}
