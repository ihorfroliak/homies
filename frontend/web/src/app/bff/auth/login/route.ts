import { cookies } from "next/headers";

import { backendFetch } from "@/server/backend";
import { currentContext } from "@/server/bff";
import { checkCsrf } from "@/server/csrf";
import { serverEnv } from "@/server/env";
import { writeSession, type TokenPair } from "@/server/session";

export const dynamic = "force-dynamic";

/**
 * Sign in: the credentials go to the backend once; the token pair is written to
 * httpOnly cookies and never returned to the browser. Backend refusals (401
 * generic, 429 with Retry-After) pass through unchanged so the UI shows the
 * same wording for unknown e-mail and wrong password.
 */
export async function POST(request: Request): Promise<Response> {
  if (!checkCsrf("POST", request.headers, serverEnv().publicOrigin).ok) {
    return Response.json({ detail: "Cross-site request refused" }, { status: 403 });
  }
  let payload: { email?: unknown; password?: unknown };
  try {
    payload = (await request.json()) as typeof payload;
  } catch {
    return Response.json({ detail: "Invalid body" }, { status: 422 });
  }
  if (typeof payload.email !== "string" || typeof payload.password !== "string") {
    return Response.json({ detail: "Invalid body" }, { status: 422 });
  }
  const ctx = await currentContext();
  let upstream: Response;
  try {
    upstream = await backendFetch("/v1/auth/login", {
      method: "POST",
      ctx: { clientIp: ctx.clientIp, requestId: ctx.requestId },
      body: JSON.stringify({ email: payload.email, password: payload.password }),
      contentType: "application/json",
    });
  } catch {
    return Response.json({ detail: "Upstream unavailable" }, { status: 502 });
  }
  const noStore = { "cache-control": "no-store" };
  if (!upstream.ok) {
    const headers = new Headers({ ...noStore, "content-type": "application/json" });
    const retry = upstream.headers.get("retry-after");
    if (retry) headers.set("retry-after", retry);
    return new Response(upstream.body, { status: upstream.status, headers });
  }
  writeSession(await cookies(), (await upstream.json()) as TokenPair);
  return Response.json({ authenticated: true }, { headers: noStore });
}
