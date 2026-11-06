import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { connection } from "next/server";
import type { ReactNode } from "react";

import "../../../design-system/tokens.css";
import "../../../design-system/components.css";
import "./globals.css";

import { SiteFooter } from "@/components/site-footer";
import { EngagementProvider } from "@/engagement/session";
import { SavedProvider } from "@/engagement/saved";
import { ListingOriginTracker } from "@/components/listing/listing-origin-tracker";
import { SiteHeader } from "@/components/site-header";
import { t } from "@/i18n";
import { pageMetadata } from "@/seo";

const publicSans = localFont({
  src: "./fonts/PublicSans.ttf", variable: "--font-public-sans",
  weight: "100 900", display: "swap",
});
const bricolage = localFont({
  src: "./fonts/BricolageGrotesque.ttf", variable: "--font-bricolage",
  weight: "200 800", display: "swap",
});

export const metadata: Metadata = {
  ...pageMetadata({ page: { kind: "home" } }),
  applicationName: t.meta.siteName,
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#faf7f0",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The CSP nonce is per request, so every page renders dynamically; a static
  // page would ship scripts without the nonce and be blocked in production.
  await connection();
  return (
    <html lang="pl" data-theme="light" className={`${publicSans.variable} ${bricolage.variable}`}>
      <body>
        <a className="skip-link" href="#tresc">
          {t.a11y.skipToContent}
        </a>
        <ListingOriginTracker />
        <EngagementProvider><SavedProvider><SiteHeader />
        <main id="tresc" tabIndex={-1}>
          {children}
        </main>
        <SiteFooter /></SavedProvider></EngagementProvider>
      </body>
    </html>
  );
}
