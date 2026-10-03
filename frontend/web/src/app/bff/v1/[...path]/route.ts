import { backendFetch } from "@/server/backend";
import { currentContext, withSession } from "@/server/bff";
import { matchRoute, safeApiPath } from "@/server/bff-routes";
import { checkCsrf } from "@/server/csrf";
import { serverEnv } from "@/server/env";

/**
 * BFF proxy: /bff/v1/... → backend /v1/... for allowlisted routes only, with the
 * session cookie turned into a bearer token on the server. Responses are never
 * cached by intermediaries (they can be personal).
 */
export const dynamic = "force-dynamic";

const PASS_RESPONSE_HEADERS = ["content-type", "retry-after", "x-request-id", "etag"];
const MAX_BODY_BYTES = 64 * 1024;

type Params = { params: Promise<{ path: string[] }> };

async function handle(request: Request, { params }: Params): Promise<Response> {
  const { path: segments } = await params;
  const path = safeApiPath(["v1", ...segments]);
  const route = path ? matchRoute(request.method, path) : undefined;
  if (!path || !route) return Response.json({ detail: "Not found" }, { status: 404 });

  const csrf = checkCsrf(request.method, request.headers, serverEnv().publicOrigin);
  if (!csrf.ok) return Response.json({ detail: "Cross-site request refused" }, { status: 403 });

  let body: ArrayBuffer | null = null;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_BODY_BYTES) return Response.json({ detail: "Request too large" }, { status: 413 });
  }

  const search = new URL(request.url).search;
  const ctx = await currentContext();
  let upstream: Response;
  try {
    upstream = await withSession(ctx, route.auth, (accessToken) =>
      backendFetch(`${path}${search}`, {
        method: request.method,
        ctx: { ...ctx, accessToken },
        body,
        contentType: request.headers.get("content-type"),
        signal: request.signal,
      }),
    );
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    return Response.json(
      { detail: timedOut ? "Upstream timeout" : "Upstream unavailable" },
      { status: timedOut ? 504 : 502, headers: { "cache-control": "no-store", "x-request-id": ctx.requestId } },
    );
  }

  const headers = new Headers({ "cache-control": "no-store" });
  for (const name of PASS_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
