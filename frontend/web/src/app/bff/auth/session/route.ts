import { backendFetch } from "@/server/backend";
import { currentContext, withSession } from "@/server/bff";

export const dynamic = "force-dynamic";

/** Who is signed in on this device: `{authenticated, user?}`; refreshes the session when needed. */
export async function GET(): Promise<Response> {
  const ctx = await currentContext();
  const noStore = { "cache-control": "no-store" };
  if (!ctx.accessToken && !ctx.refreshToken) return Response.json({ authenticated: false }, { headers: noStore });
  let upstream: Response;
  try {
    upstream = await withSession(ctx, "required", (accessToken) =>
      backendFetch("/v1/me", { method: "GET", ctx: { ...ctx, accessToken } }),
    );
  } catch {
    return Response.json({ detail: "Upstream unavailable" }, { status: 502, headers: noStore });
  }
  if (upstream.status === 401) return Response.json({ authenticated: false }, { headers: noStore });
  if (!upstream.ok) return Response.json({ detail: "Upstream error" }, { status: 502, headers: noStore });
  const user = (await upstream.json()) as { id: string; full_name: string; role: string; email_verified_at: string | null; phone: string | null };
  // Only what the UI needs; e-mail and phone stay on the account page's own call.
  return Response.json(
    { authenticated: true, user: { id: user.id, name: user.full_name, role: user.role, emailVerified: user.email_verified_at !== null, phoneVerified: user.phone !== null } },
    { headers: noStore },
  );
}
