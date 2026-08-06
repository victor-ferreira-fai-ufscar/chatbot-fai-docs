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
  // maxDiffPixels 0: os screenshots do desktop-baseline são a prova de que o layout
  // desktop não mudou durante a iniciativa mobile. Divergiu = código errado
  // (nunca regenerar o snapshot para "ficar verde" — ver tests/desktop-baseline.spec.ts).
  expect: { timeout: 120_000, toHaveScreenshot: { maxDiffPixels: 0 } },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    actionTimeout: 30_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
  },
  projects: [
    // Desktop: os specs pré-existentes rodam exatamente como antes (mesmo nome de
    // project = mesmos snapshots); só NÃO pega os specs mobile-*.
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: /mobile-.*\.spec\.ts/ },
    // Mobile: só os specs mobile-* (os antigos assumem sidebar visível, que em
    // telas estreitas vive dentro da gaveta — fluxos equivalentes têm versão própria).
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] }, testMatch: /mobile-.*\.spec\.ts/ },
    // TODO: project { name: "mobile-webkit", use: devices["iPhone 13"] } — o webkit
    // não lança nesta máquina (faltam libs de sistema: libgtk-4, libgstreamer, etc.;
    // exigiria `sudo npx playwright install-deps webkit`). Comportamentos exclusivos
    // do iOS real (dvh do Safari, teclado virtual) ficam no QA manual em aparelho.
  ],
});
