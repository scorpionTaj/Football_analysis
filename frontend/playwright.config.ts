import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://127.0.0.1:3001',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'NEXT_DIST_DIR=.next-e2e npm run dev -- --hostname 127.0.0.1 --port 3001',
    url: 'http://127.0.0.1:3001/matches',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
