import { cookies } from "next/headers";

import { checkCsrf } from "@/server/csrf";
import { serverEnv } from "@/server/env";
import { clearSession } from "@/server/session";

export const dynamic = "force-dynamic";

/**
 * Sign out on this device: both cookies are cleared. The backend has no logout
 * or revocation endpoint yet, so the refresh token itself stays valid until it
 * expires (30 days) — recorded as backend gap BG-1 in FE-001 §8. The browser
 * never held the token, so clearing the cookies removes this device's access.
 */
export async function POST(request: Request): Promise<Response> {
  if (!checkCsrf("POST", request.headers, serverEnv().publicOrigin).ok) {
    return Response.json({ detail: "Cross-site request refused" }, { status: 403 });
  }
  clearSession(await cookies());
  return Response.json({ authenticated: false }, { headers: { "cache-control": "no-store" } });
}
