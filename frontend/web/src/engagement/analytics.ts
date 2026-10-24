"use client";
import { browserAnalytics } from "@/analytics/client";
import type { EventName, EventProps } from "@/analytics/catalogue";
import { ENGAGEMENT_API_ROUTES } from "@/analytics/catalogue";
import type { ApiError } from "@/api/errors";
/** Existing consent gate and closed catalogue remain the only emission path. */
export function trackEngagement<N extends EventName>(name: N, props: EventProps<N>, route = "/oferta/[id]") { browserAnalytics().analytics.track(name, props, { route }); }
export function engagementRoute(path: string): string | undefined {
  const pathname = path.split("?")[0]!;
  return ENGAGEMENT_API_ROUTES.find(template => template === pathname || template.includes("[id]") && new RegExp(`^${template.replace("[id]", "[A-Za-z0-9-]{1,64}")}$`).test(pathname));
}
export function trackApiError(path: string, error: ApiError) {
  const route_template = engagementRoute(path);
  if (typeof window !== "undefined" && route_template) trackEngagement("engagement_api_error", { route_template, status: error.status ?? 0, code: error.code ?? "none", kind: error.kind });
}
