/** Same acceptance rule as the backend (app/core/request_id.py): a sane caller id or a fresh one. */
export const REQUEST_ID_HEADER = "x-request-id";

const SANE = /^[A-Za-z0-9._-]{8,64}$/;

export function requestIdFrom(headers: Headers): string {
  const given = headers.get(REQUEST_ID_HEADER);
  return given && SANE.test(given) ? given : crypto.randomUUID();
}
