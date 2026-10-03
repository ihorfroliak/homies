/** Liveness of the web process only (the backend has its own /healthz and /readyz). */
export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ status: "ok" }, { headers: { "cache-control": "no-store" } });
}
