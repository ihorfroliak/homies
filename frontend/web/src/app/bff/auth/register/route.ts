import { cookies } from "next/headers";
import { backendFetch } from "@/server/backend";
import { readCapped } from "@/server/body";
import { currentContext } from "@/server/bff";
import { checkCsrf } from "@/server/csrf";
import { serverEnv } from "@/server/env";
import { writeSession, type TokenPair } from "@/server/session";
export const dynamic = "force-dynamic";
const noStore = { "cache-control": "no-store" };
export async function POST(request: Request): Promise<Response> {
  if (!checkCsrf("POST", request.headers, serverEnv().publicOrigin).ok) return Response.json({ detail: "Cross-site request refused" }, { status: 403, headers: noStore });
  let payload: Record<string, unknown>;
  try {
    const raw = await readCapped(request, 4096);
    if (raw === null) return Response.json({ detail: "Request too large" }, { status: 413, headers: noStore });
    const parsed: unknown = JSON.parse(new TextDecoder().decode(raw));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
    payload = parsed as Record<string, unknown>;
  } catch { return Response.json({ detail: "Invalid body" }, { status: 422, headers: noStore }); }
  if (typeof payload.email !== "string" || typeof payload.password !== "string" || (payload.full_name !== undefined && typeof payload.full_name !== "string")) return Response.json({ detail: "Invalid body" }, { status: 422, headers: noStore });
  const ctx = await currentContext();
  const credentials = { email: payload.email, password: payload.password };
  try {
    const registered = await backendFetch("/v1/auth/register", { method: "POST", ctx: { clientIp: ctx.clientIp, requestId: ctx.requestId }, body: JSON.stringify({ ...credentials, full_name: payload.full_name ?? "" }), contentType: "application/json" });
    if (!registered.ok) return refused(registered);
    const loggedIn = await backendFetch("/v1/auth/login", { method: "POST", ctx: { clientIp: ctx.clientIp, requestId: ctx.requestId }, body: JSON.stringify(credentials), contentType: "application/json" });
    if (!loggedIn.ok) return refused(loggedIn);
    writeSession(await cookies(), await loggedIn.json() as TokenPair);
    return Response.json({ authenticated: true }, { headers: noStore });
  } catch { return Response.json({ detail: "Upstream unavailable" }, { status: 502, headers: noStore }); }
}
function refused(upstream: Response): Response {
  const headers = new Headers({ ...noStore, "content-type": "application/json" });
  const retry = upstream.headers.get("retry-after");
  if (retry) headers.set("retry-after", retry);
  return new Response(upstream.body, { status: upstream.status, headers });
}
