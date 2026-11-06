"use client";

import { useEffect } from "react";

/**
 * Closes the filter disclosure on Escape or a click outside it. Without
 * JavaScript the native summary toggle still opens and closes it.
 */
export function DismissDetails({ detailsId }: { detailsId: string }) {
  useEffect(() => {
    const details = document.getElementById(detailsId) as HTMLDetailsElement | null;
    if (!details) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !details.open) return;
      details.open = false;
      details.querySelector("summary")?.focus();
    };
    const onClick = (event: MouseEvent) => {
      if (details.open && event.target instanceof Node && !details.contains(event.target)) details.open = false;
    };
    details.addEventListener("keydown", onKey);
    document.addEventListener("click", onClick);
    return () => {
      details.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onClick);
    };
  }, [detailsId]);
  return null;
}
