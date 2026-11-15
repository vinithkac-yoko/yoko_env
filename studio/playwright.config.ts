import { defineConfig } from "@playwright/test";

// The smoke test runs the real app (API + built studio) on a throwaway SQLite database.
// Build the studio first (npm run build). Locally and in CI, Chromium comes from
// PLAYWRIGHT_CHROMIUM if set (the cloud machines have one preinstalled), else Playwright's own.
const port = 8765;
const db = `${process.env.TMPDIR ?? "/tmp"}/yoko-e2e-${Date.now()}.db`;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${port}`,
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM } : {},
    viewport: { width: 1400, height: 900 },
  },
  webServer: {
    command: `uv run yoko serve --port ${port}`,
    cwd: "..",
    url: `http://localhost:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      DATABASE_URL: `sqlite:///${db}`,
      STUDIO_TOKEN: "e2e-token",
      SESSION_SECRET: "e2e-secret",
      YOKO_STUDIO_DIST: "studio/dist",
    },
  },
});
