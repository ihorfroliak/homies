"use client";

import { useEffect } from "react";

/** Submits the enclosing form when the select changes (progressive enhancement of a GET form). */
export function AutoSubmit({ selectId }: { selectId: string }) {
  useEffect(() => {
    const select = document.getElementById(selectId) as HTMLSelectElement | null;
    if (!select) return;
    const onChange = () => select.form?.requestSubmit();
    // A page restored from the back/forward cache must show what its URL says.
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) select.form?.reset();
    };
    select.addEventListener("change", onChange);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      select.removeEventListener("change", onChange);
      window.removeEventListener("pageshow", onPageShow);
    };
  }, [selectId]);
  return null;
}
