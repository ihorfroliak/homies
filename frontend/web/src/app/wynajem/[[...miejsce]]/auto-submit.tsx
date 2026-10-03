"use client";

import { useEffect } from "react";

/** Submits the enclosing form when the select changes (progressive enhancement of a GET form). */
export function AutoSubmit({ selectId }: { selectId: string }) {
  useEffect(() => {
    const select = document.getElementById(selectId) as HTMLSelectElement | null;
    if (!select) return;
    const onChange = () => select.form?.requestSubmit();
    select.addEventListener("change", onChange);
    return () => select.removeEventListener("change", onChange);
  }, [selectId]);
  return null;
}
