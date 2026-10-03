/**
 * The end user's IP as seen by the web server, for forwarding to the backend
 * rate limiter. Same rule as the backend's `client_ip` (app/core/ratelimit.py):
 * X-Forwarded-For is trusted only for the declared number of proxy hops; with
 * 0 hops the socket address is used. Returns undefined when unknown.
 *
 * The backend then runs with TRUST_PROXY_HOPS=1 and must be reachable only from
 * this web server (and the edge for /v1/media) — docs/frontend/FE-001-foundation.md §4.
 */
export function clientIp(forwardedFor: string | null, socketIp: string | undefined, trustProxyHops: number): string | undefined {
  if (trustProxyHops > 0 && forwardedFor) {
    const parts = forwardedFor.split(",").map((p) => p.trim()).filter(Boolean);
    if (parts.length >= trustProxyHops) return sane(parts[parts.length - trustProxyHops]);
    return undefined; // fewer hops than declared: the header is not from our proxies
  }
  return sane(socketIp);
}

const IPV4 = /^(\d{1,3})(\.\d{1,3}){3}$/;
const IPV6 = /^[0-9a-fA-F:.]{2,45}$/;

function sane(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const v = value.trim();
  if (IPV4.test(v) && v.split(".").every((o) => Number(o) <= 255)) return v;
  if (v.includes(":") && IPV6.test(v)) return v;
  return undefined;
}
