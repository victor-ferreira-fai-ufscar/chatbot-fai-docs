import { test, expect, Page } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * Baseline de NÃO-REGRESSÃO do layout desktop (project chromium, 1280×720).
 *
 * Duas camadas que se protegem mutuamente:
 *   1. Screenshots pixel-perfect (maxDiffPixels 0) de 8 estados-chave — rede ampla;
 *   2. Contrato geométrico (larguras exatas das colunas) — não se "auto-atualiza"
 *      com --update-snapshots, então protege contra regenerar snapshot para
 *      esconder uma regressão.
 *
 * Regras da iniciativa mobile:
 *   - `--update-snapshots` é PROIBIDO fora da fase 0 (baseline inicial). Se um
 *     screenshot divergir, o código está errado, não o snapshot.
 *   - Rodar SEMPRE contra build de produção (`npm run build && npx next start -p 3100`)
 *     — o dev server injeta o overlay do Next e contamina pixels.
 *   - Rodar SEMPRE com BASE_URL=http://localhost:3100 (a origem aparece no modal
 *     de compartilhar; outra porta = outro pixel).
 *
 * Snapshots válidos para: chromium-1228 / @playwright/test 1.61 / next start local.
 */

const SHOT = { timeout: 15_000 } as const; // não herdar os 120s do expect global

const CONVERSATIONS = [{ id: 7, title: "Conversa de referência" }];

const SHARED = {
  title: "Conversa compartilhada de referência",
  messages: [
    { role: "user", content: "pergunta de referência" },
    {
      role: "assistant",
      content: "resposta de referência com **markdown**",
      metadata: { sources: ["- Manual do Coordenador.pdf (pág. 12 · 96%)"] },
    },
  ],
};

// Âncora de estabilidade: a bolinha de status saiu de "Verificando…" (pulse) para
// o estado final mockado ("Online"), visível no rodapé da sidebar expandida.
async function waitStable(page: Page) {
  await expect(page.getByText("Online", { exact: true })).toBeVisible();
}

test.describe("Baseline desktop — screenshots pixel-perfect", () => {
  test("01 welcome com sidebar expandida", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await expect(page.getByTestId("welcome-message")).toBeVisible();
    await waitStable(page);
    await expect(page).toHaveScreenshot("01-welcome-expandida.png", SHOT);
  });

  test("02 sidebar colapsada", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByRole("button", { name: "Minimizar menu" }).click();
    // Espera a transição de 300ms terminar (largura estável em 64px).
    const aside = page.locator("aside").first();
    await expect.poll(async () => (await aside.boundingBox())?.width).toBe(64);
    await expect(page).toHaveScreenshot("02-sidebar-colapsada.png", SHOT);
  });

  test("03 conversa com fontes e painel populado", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByTestId("suggestion-chip").first().click();
    await expect(page.getByTestId("message-done")).toBeVisible();
    await expect(page.getByTestId("assistant-content")).toContainText("R$ 17.600,00");
    await expect(page.getByTestId("source-chip").first()).toBeVisible();
    // Painel de fontes populado: um card por página citada, com o trecho carregado.
    await expect(page.getByText("Pág. 12").first()).toBeVisible();
    await expect(page.getByText(/Trecho determinístico/).first()).toBeVisible();
    await expect(page).toHaveScreenshot("03-conversa-com-fontes.png", SHOT);
  });

  test("04 sidebar em modo configurações", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByRole("button", { name: "Configurações" }).click();
    // Default = ragEngine "LightRAG (Grafo)" → o ramo renderizado mostra "Modo LightRAG".
    await expect(page.getByText("Modo LightRAG")).toBeVisible();
    await expect(page).toHaveScreenshot("04-configuracoes.png", SHOT);
  });

  test("05 modal 'Sobre a Lina'", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByTestId("welcome-message").getByRole("button", { name: "Sobre a Lina" }).click();
    await expect(page.getByRole("dialog").getByText("Assistente Virtual · FAI-UFSCar")).toBeVisible();
    await expect(page).toHaveScreenshot("05-modal-sobre-a-lina.png", SHOT);
  });

  test("06 modal de compartilhar conversa", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByRole("button", { name: "Compartilhar conversa: Conversa de referência" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Compartilhar conversa")).toBeVisible();
    await expect(dialog.getByRole("textbox", { name: "Link de compartilhamento" })).toHaveValue(
      /\/shared\/tok-mock-123$/
    );
    await expect(page).toHaveScreenshot("06-modal-compartilhar.png", SHOT);
  });

  test("07 modal 'Como utilizar'", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByRole("button", { name: "Como utilizar" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page).toHaveScreenshot("07-modal-como-utilizar.png", SHOT);
  });

  test("08 página de conversa compartilhada", async ({ page }) => {
    await mockApi(page, { shared: SHARED });
    await page.goto("/shared/tok-mock-123");
    await expect(page.getByText("Conversa compartilhada de referência")).toBeVisible();
    await expect(page.getByText("resposta de referência")).toBeVisible();
    await expect(page.getByText("Somente leitura")).toBeVisible();
    await expect(page).toHaveScreenshot("08-pagina-compartilhada.png", SHOT);
  });
});

test.describe("Contrato geométrico do desktop", () => {
  test("3 colunas com larguras exatas e sem vazamento horizontal", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);

    // Exatamente 2 <aside> (sidebar + painel de fontes), ambos visíveis.
    const asides = page.locator("aside");
    await expect(asides).toHaveCount(2);
    const sidebar = await asides.first().boundingBox();
    const sources = await asides.last().boundingBox();
    expect(sidebar?.width).toBe(256); // w-64 expandida
    expect(sources?.width).toBe(320); // w-80 painel de fontes

    // Sem vazamento horizontal no documento.
    const overflow = await page.evaluate(() => {
      const d = document.scrollingElement!;
      return d.scrollWidth - d.clientWidth;
    });
    expect(overflow).toBe(0);

    // Superfícies exclusivas de mobile NUNCA visíveis em 1280px (hoje o FAB existe
    // com lg:hidden; o header/hambúrguer passará a existir nas fases seguintes).
    await expect(page.getByTestId("mobile-menu-button")).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Ver fontes" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Abrir menu" })).not.toBeVisible();
  });

  test("sidebar colapsada mede exatamente 64px", async ({ page }) => {
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);
    await page.getByRole("button", { name: "Minimizar menu" }).click();
    const aside = page.locator("aside").first();
    await expect.poll(async () => (await aside.boundingBox())?.width).toBe(64); // w-16
  });

  test("modais centrais medem 512px em 1280px (twMerge: sm:max-w-lg prevalece)", async ({ page }) => {
    // Trava a largura ATUAL dos 3 modais no desktop — a correção de full-bleed
    // mobile (max-sm:) não pode alterar nada aqui.
    await mockApi(page, { conversations: CONVERSATIONS });
    await page.goto("/");
    await waitStable(page);

    // Modal "Como utilizar" (Sidebar). expect.poll: espera a animação de entrada
    // (zoom-in-95) assentar antes de medir — boundingBox inclui o transform.
    await page.getByRole("button", { name: "Como utilizar" }).click();
    let dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect.poll(async () => (await dialog.boundingBox())?.width).toBe(512);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);

    // Modal "Sobre a Lina" (ChatWindow).
    await page.getByTestId("welcome-message").getByRole("button", { name: "Sobre a Lina" }).click();
    dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect.poll(async () => (await dialog.boundingBox())?.width).toBe(512);
  });
});
