import type { Metadata } from "next";
import Link from "next/link";

import { t } from "@/i18n";
import { pageMetadata } from "@/seo";

export const metadata: Metadata = pageMetadata({ title: t.errors.notFoundTitle, page: { kind: "error" } });

/** 404 — never 410, and never says "usunięta" or "wygasła" (DESIGN-001 §7). */
export default function NotFound() {
  return (
    <div className="container state" role="region" aria-labelledby="nf-title">
      <h1 id="nf-title">{t.errors.notFoundTitle}</h1>
      <p>{t.errors.notFoundBody}</p>
      <Link className="btn btn--primary" href="/wynajem">
        {t.errors.notFoundAction}
      </Link>
    </div>
  );
}
