"use client";

import { t } from "@/i18n";

/**
 * Route error boundary. Shows the digest as the request code so support can
 * find the server log line; the error message itself is never rendered (it
 * may carry internals).
 */
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="container state" role="alert">
      <h1>{t.errors.genericTitle}</h1>
      <p>{t.errors.genericBody}</p>
      {error.digest ? (
        <p className="small muted">
          {t.errors.requestCode}: <code>{error.digest}</code>
        </p>
      ) : null}
      <button type="button" className="btn btn--primary" onClick={reset}>
        {t.errors.retry}
      </button>
    </div>
  );
}
