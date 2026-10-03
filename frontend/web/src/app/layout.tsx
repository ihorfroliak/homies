import type { Metadata, Viewport } from "next";
import { connection } from "next/server";
import type { ReactNode } from "react";

import "../../../design-system/tokens.css";
import "../../../design-system/components.css";
import "./globals.css";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { t } from "@/i18n";
import { pageMetadata } from "@/seo";

export const metadata: Metadata = {
  ...pageMetadata({ page: { kind: "home" } }),
  applicationName: t.meta.siteName,
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0c7d5e",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The CSP nonce is per request, so every page renders dynamically; a static
  // page would ship scripts without the nonce and be blocked in production.
  await connection();
  return (
    <html lang="pl" data-theme="light">
      <body>
        <a className="skip-link" href="#tresc">
          {t.a11y.skipToContent}
        </a>
        <SiteHeader />
        <main id="tresc" tabIndex={-1}>
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
