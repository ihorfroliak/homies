import { t } from "@/i18n";

import type { ApiError } from "./errors";

/** User-facing Polish copy for an ApiError (DESIGN-001 §5 state tables). */
export function errorMessage(error: ApiError): string {
  switch (error.kind) {
    case "network":
      return t.errors.network;
    case "timeout":
      return t.errors.timeout;
    case "rate_limited":
      return t.errors.rateLimited;
    case "unavailable":
      return t.errors.unavailable;
    case "outcome_unknown":
      return t.errors.outcomeUnknown;
    case "unauthorized":
      return t.errors.unauthorized;
    case "forbidden":
      return t.errors.forbidden;
    case "validation":
      return t.errors.validation;
    case "conflict":
      return t.errors.conflict;
    case "not_found":
      return t.errors.notFoundTitle;
    case "server":
      return t.errors.genericBody;
  }
}
