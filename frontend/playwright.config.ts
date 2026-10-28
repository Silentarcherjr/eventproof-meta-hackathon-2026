import { defineConfig, devices } from "@playwright/test";

// Smoke test of the studio UI. The backend API is mocked with a recorded real run (e2e/fixtures),
// so CI never calls Meta models; the live path is verified manually and recorded in docs/evidence.
export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: { baseURL: "http://localhost:3100", ...devices["Desktop Chrome"] },
  webServer: {
    command: "npm run build && npx next start -p 3100",
    url: "http://localhost:3100",
    timeout: 180_000,
    reuseExistingServer: false,
    env: { NEXT_PUBLIC_API_URL: "http://api.test", NEXT_DIST_DIR: ".next-e2e" },
  },
});
