"use client";
import { browserAnalytics } from "@/analytics/client";
import type { EventName, EventProps } from "@/analytics/catalogue";
/** Existing consent gate and closed catalogue remain the only emission path. */
export function trackEngagement<N extends EventName>(name: N, props: EventProps<N>, route = "/oferta/[id]") { browserAnalytics().analytics.track(name, props, { route }); }
