/**
 * Read a request body with a hard byte cap: a declared Content-Length over the
 * cap is refused before reading, and an undeclared (chunked) body is cut off as
 * soon as it passes the cap. Returns null when the body is too large. Nothing
 * unbounded is ever buffered (P3 hardening, PROGRAM-001 security review).
 */
export async function readCapped(request: Request, maxBytes: number): Promise<Uint8Array<ArrayBuffer> | null> {
  const declared = request.headers.get("content-length");
  if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > maxBytes)) return null;
  if (!request.body) return new Uint8Array(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maxBytes) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const out = new Uint8Array(size);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.byteLength;
  }
  return out;
}
