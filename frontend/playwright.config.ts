import { defineConfig, devices } from "@playwright/test";

/**
 * Testes E2E de precisão do chatbot da FAI (dirige a UI real).
 *
 * Pré-requisitos:
 *   - stack no ar: `docker compose up -d` (frontend em :3000, backend em :8000)
 *   - browser do Playwright: `npx playwright install --with-deps chromium`
 *
 * Rodar:           npx playwright test
 *   subconjunto:   E2E_LIMIT=5 npx playwright test
 *   ver relatório: npx playwright show-report
 *
 * Serializado (workers=1) porque o backend processa 1 requisição por vez (MAX_ASYNC=1);
 * cada resposta do modelo leva ~15-60s, daí os timeouts altos.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 150_000, // por teste (uma pergunta = 1 resposta do modelo)
  expect: { timeout: 120_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    actionTimeout: 30_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
