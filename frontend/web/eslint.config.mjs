import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  {
    ignores: [".next/**", "node_modules/**", "playwright-report/**", "test-results/**",
      "src/api/schema.d.ts", "next-env.d.ts"],
  },
  {
    rules: {
      // Vendor tracking stays behind src/analytics (PRIVACY-CONSENT-v1 §2).
      "no-restricted-imports": ["error", {
        patterns: [{ group: ["*gtag*", "*google-analytics*", "*facebook*", "*meta-pixel*", "*segment*"],
          message: "No vendor tracking SDK (founder G-12); use src/analytics." }],
      }],
    },
  },
];

export default config;
