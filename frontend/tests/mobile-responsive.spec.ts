import { test, expect, Page } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * Suite de responsividade MOBILE (project mobile-chromium, Pixel 7: 412×915,
 * touch). Roda só neste project (testMatch /mobile-/ no playwright.config.ts) —
 * os specs desktop pré-existentes NÃO rodam em viewport estreito porque assumem
 * a sidebar visível (aqui ela vive dentro da gaveta).
 *
 * Comportamentos exclusivos do iOS real (dvh do Safari, teclado virtual,
 * interactive-widget) ficam no QA manual em aparelho — o Playwright não simula
 * teclado virtual. O que este spec garante é o pré-requisito de layout.
 *
 * Rodar: BASE_URL=http://localhost:3100 npx playwright test --project=mobile-chromium
 */

// Cenário "estressado": tabela GFM larga + código inquebrável + 8 fontes
// (aciona o agrupamento de chips com intervalos de páginas).
const STRESS_ANSWER = [
  "Segue o resumo em tabela:",
  "",
  "| Documento | Página | Limite | Categoria | Observação longa | Vigência |",
  "|---|---|---|---|---|---|",
  "| Manual do Coordenador.pdf | 26 | R$ 17.600,00 | Contratação direta de serviços | Deve-se evitar o fracionamento de despesa conforme norma | 2026 |",
  "| Manual do Sistema.pdf | 59 | R$ 8.800,00 | Compras | Aplicável a materiais de consumo com recursos públicos | 2026 |",
  "",
  "Código de referência: `PROCESSO-FAI-2026-000123456789-ABCDEFGH`",
].join("\n");

const STRESS_SOURCES = [
  "- Manual do Coordenador.pdf (pág. 26 · 96%)",
  "- Manual do Coordenador.pdf (pág. 27 · 92%)",
  "- Manual do Coordenador.pdf (pág. 28 · 90%)",
  "- Manual do Coordenador.pdf (pág. 29 · 88%)",
  "- Manual do Coordenador.pdf (pág. 30 · 85%)",
  "- Manual do Coordenador.pdf (pág. 31 · 82%)",
  "- Manual_do_Sistema_Area_Coordenadores.pdf (pág. 59 · 96%)",
  "- Manual_do_Sistema_Area_Coordenadores.pdf (pág. 60 · 90%)",
];

const SHARED = {
  title: "Conversa compartilhada de referência",
  messages: [
    { role: "user", content: "pergunta de referência" },
    {
      role: "assistant",
      content: STRESS_ANSWER,
      metadata: { sources: STRESS_SOURCES },
    },
  ],
};

// Sem estouro horizontal no documento E na área de mensagens. scrollWidth enxerga
// conteúdo clipado mesmo sob overflow-hidden — pega vazamento invisível.
async function expectNoHorizontalOverflow(page: Page, { messages = true } = {}) {
  const doc = await page.evaluate(() => {
    const d = document.scrollingElement!;
    return d.scrollWidth - d.clientWidth;
  });
  expect(doc, "estouro horizontal no documento").toBeLessThanOrEqual(0);
  if (messages) {
    const msgs = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="messages-container"]');
      return el ? el.scrollWidth - el.clientWidth : 0;
    });
    expect(msgs, "estouro horizontal na área de mensagens").toBeLessThanOrEqual(0);
  }
}

// Envia uma pergunta e espera a resposta mockada concluir.
async function sendAndAwait(page: Page, question = "teste de layout") {
  await page.getByTestId("chat-input").fill(question);
  await page.getByTestId("chat-send").tap();
  await expect(page.getByTestId("message-done")).toBeVisible();
}

// Erros de página (inclui erro de hidratação minificado do React) falham o teste.
let pageErrors: string[] = [];
test.beforeEach(async ({ page }) => {
  pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));
});
test.afterEach(() => {
  expect(pageErrors, "erros de runtime/hidratação na página").toEqual([]);
});

test.describe("Welcome e navegação", () => {
  test("welcome sem estouro; hambúrguer visível; sidebar desktop oculta; chips full-width", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await expect(page.getByTestId("welcome-message")).toBeVisible();

    await expectNoHorizontalOverflow(page);
    await expect(page.getByTestId("mobile-menu-button")).toBeVisible();
    // A sidebar desktop segue no DOM, mas display:none abaixo de lg.
    await expect(page.locator("aside").first()).toBeHidden();

    const viewport = page.viewportSize()!;
    const chips = page.getByTestId("suggestion-chip");
    await expect(chips).toHaveCount(3);
    for (let i = 0; i < 3; i++) {
      const box = await chips.nth(i).boundingBox();
      expect(box).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1);
    }
  });

  test("gaveta do menu: abre, seleciona conversa (fecha e carrega), Escape fecha", async ({ page }) => {
    await mockApi(page, {
      conversations: [{ id: 7, title: "Conversa antiga" }],
      messages: [
        { role: "user", content: "pergunta antiga" },
        { role: "assistant", content: "resposta antiga", metadata: { gen_time: 2.5 } },
      ],
    });
    await page.goto("/");

    await page.getByTestId("mobile-menu-button").tap();
    const drawer = page.locator('[data-slot="sheet-content"]');
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Nova Conversa" })).toBeVisible();

    // Selecionar conversa fecha a gaveta e carrega as mensagens.
    await drawer.getByRole("button", { name: "Conversa antiga", exact: true }).tap();
    await expect(drawer).toHaveCount(0);
    await expect(page.getByTestId("user-content")).toHaveText("pergunta antiga");

    // Reabre e fecha por Escape.
    await page.getByTestId("mobile-menu-button").tap();
    await expect(page.locator('[data-slot="sheet-content"]')).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator('[data-slot="sheet-content"]')).toHaveCount(0);
  });

  test("configurações são utilizáveis dentro da gaveta, sem estouro", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.getByTestId("mobile-menu-button").tap();
    const drawer = page.locator('[data-slot="sheet-content"]');
    await drawer.getByRole("button", { name: "Configurações" }).tap();
    await expect(drawer.getByText("Modo LightRAG")).toBeVisible();

    // Abre o primeiro select (Motor de RAG) e confere que nada vaza da viewport.
    await drawer.getByRole("combobox").first().tap();
    await expect(page.getByRole("option", { name: "LightRAG (Grafo)" })).toBeVisible();
    await expectNoHorizontalOverflow(page, { messages: false });
  });
});

test.describe("Conversa estressada (tabela + fontes)", () => {
  test("sem estouro; tabela com scroll interno; chips agrupados em intervalos", async ({ page }) => {
    await mockApi(page, { answer: STRESS_ANSWER, sources: STRESS_SOURCES });
    await page.goto("/");
    await sendAndAwait(page);

    await expectNoHorizontalOverflow(page);

    // A tabela ganha scroll interno no wrapper (overflow-x-auto), não no documento.
    const wrapperScrolls = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="assistant-content"] .overflow-x-auto');
      return el ? el.scrollWidth > el.clientWidth : null;
    });
    expect(wrapperScrolls, "wrapper de tabela existe e rola internamente").toBe(true);

    // Chips agrupados por documento com intervalos comprimidos.
    const chips = page.getByTestId("source-chip");
    await expect(chips).toHaveCount(2);
    await expect(chips.first()).toContainText("págs. 26-31");
    await expect(chips.last()).toContainText("págs. 59-60");
  });

  test("fontes: badge no header; gaveta abre pelo header e pelo botão da resposta", async ({ page }) => {
    await mockApi(page, { answer: STRESS_ANSWER, sources: STRESS_SOURCES });
    await page.goto("/");
    await sendAndAwait(page);

    // Badge com a contagem de itens (um por página citada: 8).
    await expect(page.getByTestId("mobile-sources-button")).toContainText("8");

    // Abre pelo botão "Ver fontes" da resposta.
    await page.getByTestId("message-view-sources").tap();
    const sheet = page.locator('[data-slot="sheet-content"]');
    await expect(sheet.getByText("Fontes", { exact: true })).toBeVisible();
    await expect(sheet.getByText("Pág. 26").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);

    // Abre pelo header.
    await page.getByTestId("mobile-sources-button").tap();
    await expect(page.locator('[data-slot="sheet-content"]').getByText("Fontes", { exact: true })).toBeVisible();

    // O antigo FAB flutuante não existe mais.
    await expect(page.locator('button.fixed[aria-label="Ver fontes"]')).toHaveCount(0);
  });
});

test.describe("Composer", () => {
  test("botões e textarea dentro da viewport; fonte 16px (anti-zoom iOS)", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    const viewport = page.viewportSize()!;

    for (const target of [
      page.getByTestId("chat-input"),
      page.getByTestId("chat-send"),
      page.getByRole("button", { name: "Mais opções" }),
      page.getByRole("button", { name: "Gravar pergunta por voz" }),
    ]) {
      await expect(target).toBeVisible();
      const box = await target.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.x, "elemento começa dentro da viewport").toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width, "elemento termina dentro da viewport").toBeLessThanOrEqual(viewport.width + 1);
    }

    // <16px dispara auto-zoom do iOS Safari ao focar (a checagem do CSS computado
    // vale igualmente no chromium; o comportamento de zoom em si é do iOS).
    const fontSize = await page.getByTestId("chat-input").evaluate((el) => getComputedStyle(el).fontSize);
    expect(fontSize).toBe("16px");

    // Focar/digitar não gera estouro.
    await page.getByTestId("chat-input").fill("uma pergunta razoavelmente longa para testar o comportamento do textarea em telas estreitas");
    await expectNoHorizontalOverflow(page);
  });

  test("bottom-sheet do modo agêntico: abre, toggle funciona, não fecha sozinho", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: "Mais opções" }).tap();
    const sheet = page.locator('[data-slot="sheet-content"]');
    await expect(sheet).toBeVisible();
    // exact: o SheetDescription sr-only ("Modo agêntico e envio de anexos.")
    // também conteria o texto e violaria o strict mode.
    await expect(sheet.getByText("Modo agêntico", { exact: true })).toBeVisible();

    // Toque na linha-label alterna o switch e NÃO fecha o sheet (regressão do
    // handler de mousedown-fora, que fechava em qualquer toque dentro do portal).
    const state = () => page.locator("#agentic-mode").getAttribute("data-state");
    const before = await state();
    await sheet.locator('label[for="agentic-mode"]').tap();
    await expect(sheet).toBeVisible();
    expect(await state()).not.toBe(before);

    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);
  });
});

test.describe("Modais", () => {
  test("'Sobre a Lina' com margens (não full-bleed) e fechável", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    const viewport = page.viewportSize()!;

    await page.getByTestId("welcome-message").getByRole("button", { name: "Sobre a Lina" }).tap();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect.poll(async () => (await dialog.boundingBox())?.x).toBeGreaterThanOrEqual(12);
    const box = (await dialog.boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width - 12);

    await dialog.getByRole("button", { name: "Close" }).tap();
    await expect(dialog).toHaveCount(0);
  });

  test("'Como utilizar' (aberto pela gaveta) com margens", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    const viewport = page.viewportSize()!;

    await page.getByTestId("mobile-menu-button").tap();
    await page.locator('[data-slot="sheet-content"]').getByRole("button", { name: "Como utilizar" }).tap();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect.poll(async () => (await dialog.boundingBox())?.x).toBeGreaterThanOrEqual(12);
    const box = (await dialog.boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width - 12);
    await expectNoHorizontalOverflow(page, { messages: false });
  });
});

test.describe("Página compartilhada", () => {
  test("sem estouro com tabela larga; header sticky permanece visível", async ({ page }) => {
    await mockApi(page, { shared: SHARED });
    await page.goto("/shared/tok-mock-123");
    await expect(page.getByText("Conversa compartilhada de referência")).toBeVisible();

    await expectNoHorizontalOverflow(page, { messages: false });

    // Header sticky: rola o <main> (scroll container da página) e confere que
    // o título continua visível no topo.
    await page.evaluate(() => { document.querySelector("main")!.scrollTop = 600; });
    await expect(page.getByText("Somente leitura")).toBeVisible();
    const headerBox = await page.locator("header").boundingBox();
    expect(headerBox!.y).toBeLessThanOrEqual(1);
  });
});

test.describe("Piso de 320px", () => {
  test.use({ viewport: { width: 320, height: 700 } });

  test("welcome e conversa estressada sem estouro em 320×700", async ({ page }) => {
    await mockApi(page, { answer: STRESS_ANSWER, sources: STRESS_SOURCES });
    await page.goto("/");
    await expect(page.getByTestId("welcome-message")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByTestId("chat-input").fill("teste 320px");
    await page.getByTestId("chat-send").click();
    await expect(page.getByTestId("message-done")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
