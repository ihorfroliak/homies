import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 3100);
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;

/**
 * E2E runs against a production build (`next build` first). FE-001 specs need
 * no backend; FE-002 specs need the API with the E2E seed (E2E_BACKEND=1).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [["list"], ["junit", { outputFile: "test-results/e2e-junit.xml" }]] : "list",
  use: {
    baseURL: BASE_URL,
    locale: "pl-PL",
    timezoneId: "Europe/Warsaw",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: `npm run start -- -p ${PORT}`,
        url: `${BASE_URL}/healthz`,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
        env: { PUBLIC_ORIGIN: BASE_URL, HOMIES_WEB_ENV: "development" },
      },
});
