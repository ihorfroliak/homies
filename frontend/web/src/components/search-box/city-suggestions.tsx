"use client";

import { useEffect, useState } from "react";

/** Native <datalist> suggestions for the city field: debounced 250 ms, the previous request aborted. */
export function CitySuggestions({ inputId, listId }: { inputId: string; listId: string }) {
  const [names, setNames] = useState<string[]>([]);
  useEffect(() => {
    const input = document.getElementById(inputId) as HTMLInputElement | null;
    if (!input) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    let revision = 0;
    const onInput = () => {
      clearTimeout(timer);
      controller?.abort();
      const currentRevision = ++revision;
      const q = input.value.trim();
      setNames([]);
      if (q.length < 2) return setNames([]);
      timer = setTimeout(async () => {
        const request = new AbortController();
        controller = request;
        try {
          const r = await fetch(`/bff/v1/geo/localities?country=PL&limit=8&q=${encodeURIComponent(q)}`, { signal: request.signal });
          if (!r.ok) return;
          const rows = (await r.json()) as { name: string; kind: string }[];
          if (request.signal.aborted || revision !== currentRevision || input.value.trim() !== q) return;
          setNames([...new Set(rows.filter((l) => l.kind === "CITY").map((l) => l.name))]);
        } catch {
          // suggestions are optional; the form still submits the typed name
        }
      }, 250);
    };
    input.addEventListener("input", onInput);
    return () => {
      revision++;
      clearTimeout(timer);
      controller?.abort();
      input.removeEventListener("input", onInput);
    };
  }, [inputId]);
  return (
    <datalist id={listId}>
      {names.map((n) => (
        <option key={n} value={n} />
      ))}
    </datalist>
  );
}
