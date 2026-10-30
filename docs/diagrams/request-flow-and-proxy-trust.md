# Request flow and reverse-proxy trust (private alpha, PROPOSED)

Design, not a running system. Detail:
[STAGING-ARCHITECTURE §3, §5](../production/STAGING-ARCHITECTURE.md#3-proxy-trust-and-client-ip).

```mermaid
flowchart LR
  B["Browser"] -->|"HTTPS 443, basic-auth fence"| C["Caddy 172.30.10.10"]
  C -->|"/v1/media/* — XFF set by Caddy, Cookie and Authorization removed"| A["API :8000 172.30.10.20"]
  C -->|"everything else"| W["Next.js web + BFF 172.30.10.11"]
  W -->|"/bff/v1/* allowlist — Bearer from httpOnly cookie, XFF = client"| A
  C -.->|"/metrics: 404 at the edge"| X["not routed"]
  P["Prometheus (data network)"] -->|"/metrics, not trusted for XFF"| A
```

```mermaid
flowchart TB
  R["Request reaches the API"] --> Q{"socket peer in TRUSTED_PROXY_CIDRS and TRUST_PROXY_HOPS > 0?"}
  Q -->|"no"| Peer["client = socket peer"]
  Q -->|"yes"| H{"XFF has at least HOPS entries and later hops are trusted?"}
  H -->|"no"| Peer
  H -->|"yes"| F["client = XFF entry HOPS from the right"]
```

Trusted peers: exactly Caddy and web (`/32` each). Never the Docker
gateway, the whole subnet, the worker or Prometheus. Source:
[ratelimit.py `client_ip`](../../backend/app/core/ratelimit.py),
[client-ip.ts](../../frontend/web/src/server/client-ip.ts).
