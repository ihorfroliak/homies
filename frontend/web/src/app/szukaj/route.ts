import { NextResponse } from "next/server";

import { backendClient } from "@/server/backend";
import { currentContext } from "@/server/bff";
import { serverEnv } from "@/server/env";

export const dynamic = "force-dynamic";

/**
 * The home search box submits here (a plain GET form, so it works without
 * JavaScript): the typed city name is resolved to its result page
 * ("Kraków" → /wynajem/krakow) and the cost limit carried over. An unknown
 * name lands on the national results with the cost kept, never on an error.
 */
export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const name = (url.searchParams.get("miasto") ?? "").trim().slice(0, 80);
  const cost = url.searchParams.get("koszt_do") ?? "";
  const query = /^\d{1,8}$/.test(cost) && Number(cost) > 0 ? `?koszt_do=${cost}` : "";
  let path = "/wynajem";
  if (name) {
    try {
      const ctx = await currentContext();
      const { data } = await backendClient({ clientIp: ctx.clientIp, requestId: ctx.requestId }).GET("/v1/geo/localities", { params: { query: { country: "PL", q: name, limit: 10 } } });
      const exact = data?.find((l) => l.kind === "CITY" && l.name.toLocaleLowerCase("pl") === name.toLocaleLowerCase("pl")) ?? data?.find((l) => l.kind === "CITY");
      if (exact?.slug) path = `/wynajem/${exact.slug}`;
    } catch {
      // backend unreachable: the results page shows its own error state
    }
  }
  return NextResponse.redirect(new URL(`${path}${query}`, serverEnv().publicOrigin), 303);
}
