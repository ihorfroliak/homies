"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { t } from "@/i18n";

/**
 * Route error boundary. Shows the digest as the request code so support can
 * find the server log line; the error message itself is never rendered (it
 * may carry internals). Retry asks the server again: reset() alone would only
 * re-render the same failed result.
 */
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <div className="container state" role="alert">
      <h1>{t.errors.genericTitle}</h1>
      <p>{t.errors.genericBody}</p>
      {error.digest ? (
        <p className="small muted">
          {t.errors.requestCode}: <code>{error.digest}</code>
        </p>
      ) : null}
      <button
        type="button"
        className="btn btn--primary"
        aria-busy={pending}
        disabled={pending}
        onClick={() =>
          start(() => {
            router.refresh();
            reset();
          })
        }
      >
        {t.errors.retry}
      </button>
    </div>
  );
}
