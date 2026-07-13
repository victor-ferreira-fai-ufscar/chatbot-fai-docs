import { test, expect, Page, Route } from "@playwright/test";

/**
 * Testes de UI de exportar/imprimir conversa (barra de ações no topo do chat).
 * Backend mockado no nível de rede. O endpoint export.pdf devolve um PDF fake.
 *
 * Rodar: BASE_URL=http://localhost:3100 npx playwright test tests/export-conversation.spec.ts
 */

const FAKE_PDF = "%PDF-1.4\n%mock\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF";

interface ExportCall { url: string; download: string | null; userId: string | null; }

async function mockApi(
  page: Page,
  opts: { slowExportMs?: number; slowStreamMs?: number } = {}
): Promise<{ exportCalls: ExportCall[] }> {
  const exportCalls: ExportCall[] = [];
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith("/status")) {
      return route.fulfill({ json: { lightrag: { status: "online" } } });
    }
    if (path.endsWith("/chat/stream")) {
      if (opts.slowStreamMs) await new Promise((r) => setTimeout(r, opts.slowStreamMs));
      const body = [
        `data: ${JSON.stringify({ content: "resposta de acompanhamento" })}`, "",
        `data: ${JSON.stringify({ done: true, conversation_id: 7, gen_time: 1.0, sources: [] })}`, "", "",
      ].join("\n");
      return route.fulfill({ status: 200, contentType: "text/event-stream", body });
    }
    if (/\/history\/\d+\/export\.pdf$/.test(path)) {
      exportCalls.push({
        url: url.pathname + url.search,
        download: url.searchParams.get("download"),
        userId: url.searchParams.get("user_id"),
      });
      if (opts.slowExportMs) await new Promise((r) => setTimeout(r, opts.slowExportMs));
      return route.fulfill({
        status: 200,
        contentType: "application/pdf",
        headers: { "content-disposition": 'attachment; filename="conversa-teste.pdf"' },
        body: FAKE_PDF,
      });
    }
    if (/\/history\/\d+\/messages$/.test(path)) {
      return route.fulfill({
        json: [
          { role: "user", content: "pergunta de teste" },
          { role: "assistant", content: "resposta de teste", metadata: { gen_time: 1.2 } },
        ],
      });
    }
    if (/\/history\/?$/.test(path)) {
      return route.fulfill({ json: [{ id: 7, user_id: "guest", title: "Conversa exportável", rag_engine: "LightRAG", created_at: "2026-07-13T00:00:00Z" }] });
    }
    return route.fulfill({ status: 404, json: { detail: "mock" } });
  });
  return { exportCalls };
}

test.describe("Exportar / imprimir conversa", () => {
  test("barra NÃO aparece na tela de boas-vindas (sem conversa)", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await expect(page.getByTestId("welcome-message")).toBeVisible();
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Imprimir" })).toHaveCount(0);
  });

  test("barra aparece ao abrir uma conversa salva", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Conversa exportável", exact: true }).click();
    await expect(page.getByTestId("assistant-content")).toContainText("resposta de teste");
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Imprimir" })).toBeVisible();
  });

  test("Imprimir abre o PDF inline em nova aba (sem download=true)", async ({ page }) => {
    const { exportCalls } = await mockApi(page);
    // Captura o window.open sem depender de popup real (determinístico).
    await page.addInitScript(() => {
      (window as any).__opened = [];
      window.open = ((u?: string | URL) => { (window as any).__opened.push(String(u)); return null; }) as any;
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Conversa exportável", exact: true }).click();
    await expect(page.getByTestId("assistant-content")).toBeVisible();

    await page.getByRole("button", { name: "Imprimir" }).click();
    const opened = await page.evaluate(() => (window as any).__opened as string[]);
    expect(opened).toHaveLength(1);
    expect(opened[0]).toContain("/history/7/export.pdf");
    expect(opened[0]).toContain("user_id=");
    expect(opened[0]).not.toContain("download=true");
  });

  test("Exportar baixa o PDF com download=true e nome do Content-Disposition", async ({ page }) => {
    const { exportCalls } = await mockApi(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Conversa exportável", exact: true }).click();
    await expect(page.getByTestId("assistant-content")).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Exportar PDF" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("conversa-teste.pdf");
    // A chamada de export foi com download=true e user_id.
    const exp = exportCalls.find((c) => c.download);
    expect(exp).toBeTruthy();
    expect(exp!.download).toBe("true");
    expect(exp!.userId).toBeTruthy();
  });

  test("Exportar mostra 'Exportando…', desabilita e ignora clique duplo (1 request)", async ({ page }) => {
    const { exportCalls } = await mockApi(page, { slowExportMs: 1200 });
    await page.goto("/");
    await page.getByRole("button", { name: "Conversa exportável", exact: true }).click();
    await expect(page.getByTestId("assistant-content")).toBeVisible();

    const btn = page.getByRole("button", { name: /Exportar/ });
    await btn.click();
    // Estado de carregando: rótulo muda e o botão fica desabilitado.
    await expect(page.getByRole("button", { name: "Exportando…" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Exportando…" })).toBeDisabled();
    // Clique repetido durante o carregamento não dispara nova exportação.
    await page.getByRole("button", { name: "Exportando…" }).click({ force: true }).catch(() => {});
    await page.waitForEvent("download");
    expect(exportCalls).toHaveLength(1);
    // Volta ao normal ao terminar.
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toBeEnabled();
  });

  test("barra permanece montada durante a geração (botões desabilitados, sem sumir)", async ({ page }) => {
    await mockApi(page, { slowStreamMs: 1500 });
    await page.goto("/");
    await page.getByRole("button", { name: "Conversa exportável", exact: true }).click();
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toBeVisible();

    // Envia um follow-up: durante a geração a barra NÃO some (evita flicker/salto).
    await page.getByTestId("chat-input").fill("mais uma pergunta");
    await page.getByTestId("chat-send").click();
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Imprimir" })).toBeDisabled();

    // Terminada a geração, reabilita.
    await expect(page.getByTestId("message-done").last()).toBeVisible();
    await expect(page.getByRole("button", { name: "Exportar PDF" })).toBeEnabled();
  });
});
