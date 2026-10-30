import { NextResponse } from "next/server";

import { backendClient } from "@/server/backend";
import { currentContext } from "@/server/bff";
import { serverEnv } from "@/server/env";

export const dynamic = "force-dynamic";

/**
 * The home search form submits here (a plain GET form, so it works without
 * JavaScript): the city name is resolved to its result page ("Kraków" →
 * /wynajem/krakow); an area (`obszar`) is kept only when it is one of that
 * city's areas in the geo API (→ /wynajem/krakow/kazimierz); the monthly total
 * limit and minimum rooms are carried over in the canonical parameter names.
 * An unknown city or area lands on the wider results with the filters kept,
 * never on an error.
 */
export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const name = (url.searchParams.get("miasto") ?? "").trim().slice(0, 80);
  const area = (url.searchParams.get("obszar") ?? "").trim();
  const params = new URLSearchParams();
  const cost = url.searchParams.get("koszt_do") ?? "";
  if (/^\d{1,8}$/.test(cost) && Number(cost) > 0) params.set("koszt_do", cost);
  const rooms = url.searchParams.get("pokoje_od") ?? "";
  if (/^\d{1,3}$/.test(rooms) && Number(rooms) >= 1 && Number(rooms) <= 100) params.set("pokoje_od", rooms);
  let path = "/wynajem";
  if (name) {
    try {
      const ctx = await currentContext();
      const api = backendClient({ clientIp: ctx.clientIp, requestId: ctx.requestId });
      const { data } = await api.GET("/v1/geo/localities", { params: { query: { country: "PL", q: name, limit: 10 } } });
      const exact = data?.find((l) => l.kind === "CITY" && l.name.toLocaleLowerCase("pl") === name.toLocaleLowerCase("pl")) ?? data?.find((l) => l.kind === "CITY");
      if (exact?.slug) {
        path = `/wynajem/${exact.slug}`;
        if (/^[a-z0-9-]{1,120}$/.test(area)) {
          const areas = await api.GET("/v1/geo/localities/{locality_id}/areas", { params: { path: { locality_id: exact.id } } });
          if (areas.data?.some((a) => a.slug === area)) path += `/${area}`;
        }
      }
    } catch {
      // backend unreachable: the results page shows its own error state
    }
  }
  const query = params.size > 0 ? `?${params}` : "";
  return NextResponse.redirect(new URL(`${path}${query}`, serverEnv().publicOrigin), 303);
}
