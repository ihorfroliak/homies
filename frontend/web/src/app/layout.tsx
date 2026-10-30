import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Public_Sans } from "next/font/google";
import { connection } from "next/server";
import type { ReactNode } from "react";

import "../../../design-system/tokens.css";
import "../../../design-system/components.css";
import "./globals.css";

import { SiteFooter } from "@/components/site-footer";
import { EngagementProvider } from "@/engagement/session";
import { SavedProvider } from "@/engagement/saved";
import { SiteHeader } from "@/components/site-header";
import { t } from "@/i18n";
import { pageMetadata } from "@/seo";

// 1C typography (DESIGN-001C MASTER, FE-VIS-001A). next/font downloads the
// files at build time and serves them from this origin, so visitors never
// contact Google (privacy; CSP font-src 'self'). latin-ext carries Polish.
const display = Bricolage_Grotesque({ subsets: ["latin", "latin-ext"], weight: ["600", "800"], variable: "--font-bricolage", display: "swap" });
const body = Public_Sans({ subsets: ["latin", "latin-ext"], weight: ["400", "500", "600", "700"], variable: "--font-public-sans", display: "swap" });

export const metadata: Metadata = {
  ...pageMetadata({ page: { kind: "home" } }),
  applicationName: t.meta.siteName,
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#121212",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The CSP nonce is per request, so every page renders dynamically; a static
  // page would ship scripts without the nonce and be blocked in production.
  await connection();
  return (
    <html lang="pl" data-theme="light" className={`${display.variable} ${body.variable}`}>
      <body>
        <a className="skip-link" href="#tresc">
          {t.a11y.skipToContent}
        </a>
        <EngagementProvider><SavedProvider><SiteHeader />
        <main id="tresc" tabIndex={-1}>
          {children}
        </main>
        <SiteFooter /></SavedProvider></EngagementProvider>
      </body>
    </html>
  );
}
