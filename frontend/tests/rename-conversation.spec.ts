import { test, expect, Page, Route } from "@playwright/test";

/**
 * Testes de UI do renomear conversa (ícone de lápis na Sidebar).
 * Backend mockado no nível de rede — valida só o comportamento da UI.
 *
 * Rodar: BASE_URL=http://localhost:3100 npx playwright test tests/rename-conversation.spec.ts
 */

interface PatchCall {
  id: string;
  body: Record<string, unknown>;
  userId: string | null;
}

// Intercepta a API e registra as chamadas PATCH de renomear.
// - failPatch: o PATCH responde 500 (testa rollback).
// - staleGet: o GET /history devolve os títulos ORIGINAIS (snapshot), simulando um
//   read do servidor ANTERIOR ao commit do PATCH — a corrida do poll de 15s.
async function mockApi(
  page: Page,
  opts: { failPatch?: boolean; staleGet?: boolean; initialTitles?: Array<[number, string]> } = {}
): Promise<{ patchCalls: PatchCall[]; serverTitles: Map<number, string> }> {
  const patchCalls: PatchCall[] = [];
  const serverTitles = new Map<number, string>(opts.initialTitles ?? [[7, "Conversa original"]]);
  // Snapshot dos títulos no início: é o que um GET "obsoleto" devolveria.
  const originalTitles = new Map(serverTitles);

  await page.route("**/api/v1/**", (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path.endsWith("/status")) {
      return route.fulfill({ json: { lightrag: { status: "online" } } });
    }
    const idMatch = path.match(/\/history\/(\d+)$/);
    if (idMatch && method === "PATCH") {
      const id = parseInt(idMatch[1], 10);
      const body = route.request().postDataJSON() ?? {};
      patchCalls.push({ id: idMatch[1], body, userId: url.searchParams.get("user_id") });
      if (opts.failPatch) {
        return route.fulfill({ status: 500, json: { detail: "erro simulado" } });
      }
      serverTitles.set(id, String(body.title));
      return route.fulfill({ json: { status: "success", id, title: body.title } });
    }
    if (idMatch && method === "DELETE") {
      serverTitles.delete(parseInt(idMatch[1], 10));
      return route.fulfill({ json: { status: "success" } });
    }
    if (/\/history\/?$/.test(path) && method === "GET") {
      // Membership sempre atual (respeita deletes); título obsoleto quando staleGet.
      const list = [...serverTitles.entries()].map(([id, title]) => ({
        id,
        user_id: "guest",
        title: opts.staleGet ? (originalTitles.get(id) ?? title) : title,
        rag_engine: "LightRAG",
        created_at: "2026-07-13T00:00:00Z",
      }));
      return route.fulfill({ json: list });
    }
    if (/\/history\/\d+\/messages$/.test(path)) {
      return route.fulfill({ json: [] });
    }
    return route.fulfill({ status: 404, json: { detail: "mock: rota não mapeada" } });
  });

  return { patchCalls, serverTitles };
}

test.describe("Renomear conversa (ícone de lápis)", () => {
  test("lápis abre input; Enter salva e dispara PATCH com o novo título", async ({ page }) => {
    const { patchCalls } = await mockApi(page);
    await page.goto("/");

    const row = page.getByText("Conversa original");
    await expect(row).toBeVisible();
    // O lápis fica visível no hover; o Playwright dispara os handlers mesmo assim.
    await page.getByRole("button", { name: /^Renomear conversa/ }).click();

    const input = page.getByRole("textbox", { name: "Novo título da conversa" });
    await expect(input).toBeVisible();
    await input.fill("Título editado");
    await input.press("Enter");

    // Atualização otimista: o novo título aparece; o PATCH foi com o corpo certo.
    await expect(page.getByText("Título editado")).toBeVisible();
    expect(patchCalls).toHaveLength(1);
    expect(patchCalls[0].id).toBe("7");
    expect(patchCalls[0].body.title).toBe("Título editado");
    expect(patchCalls[0].userId).toBeTruthy();
  });

  test("Escape cancela sem salvar (nenhum PATCH)", async ({ page }) => {
    const { patchCalls } = await mockApi(page);
    await page.goto("/");
    await expect(page.getByText("Conversa original")).toBeVisible();

    await page.getByRole("button", { name: /^Renomear conversa/ }).click();
    const input = page.getByRole("textbox", { name: "Novo título da conversa" });
    await input.fill("não deve salvar");
    await input.press("Escape");

    await expect(page.getByText("Conversa original")).toBeVisible();
    await expect(page.getByText("não deve salvar")).toHaveCount(0);
    expect(patchCalls).toHaveLength(0);
  });

  test("título inalterado não dispara PATCH", async ({ page }) => {
    const { patchCalls } = await mockApi(page);
    await page.goto("/");
    await expect(page.getByText("Conversa original")).toBeVisible();

    await page.getByRole("button", { name: /^Renomear conversa/ }).click();
    const input = page.getByRole("textbox", { name: "Novo título da conversa" });
    await input.press("Enter"); // salva sem alterar

    await expect(page.getByText("Conversa original")).toBeVisible();
    expect(patchCalls).toHaveLength(0);
  });

  test("falha no PATCH faz rollback para o título do servidor", async ({ page }) => {
    await mockApi(page, { failPatch: true });
    await page.goto("/");
    await expect(page.getByText("Conversa original")).toBeVisible();

    await page.getByRole("button", { name: /^Renomear conversa/ }).click();
    const input = page.getByRole("textbox", { name: "Novo título da conversa" });
    await input.fill("título que vai falhar");
    await input.press("Enter");

    // Otimista aparece brevemente, mas o refetch de rollback restaura o original.
    await expect(page.getByText("Conversa original")).toBeVisible();
    await expect(page.getByText("título que vai falhar")).toHaveCount(0);
  });

  test("botão de salvar (check) via mouse também comita", async ({ page }) => {
    const { patchCalls } = await mockApi(page);
    await page.goto("/");
    await expect(page.getByText("Conversa original")).toBeVisible();

    await page.getByRole("button", { name: /^Renomear conversa/ }).click();
    const input = page.getByRole("textbox", { name: "Novo título da conversa" });
    await input.fill("salvo pelo check");
    await page.getByRole("button", { name: "Salvar título" }).click();

    await expect(page.getByText("salvo pelo check")).toBeVisible();
    expect(patchCalls).toHaveLength(1);
    expect(patchCalls[0].body.title).toBe("salvo pelo check");
  });

  test("rename otimista sobrevive a um GET obsoleto do refetch (não reverte)", async ({ page }) => {
    // GET devolve títulos ORIGINAIS (servidor 'atrasado'); um refetch concorrente
    // NÃO pode reverter um rename já salvo — o overlay de pendentes protege.
    const { patchCalls } = await mockApi(page, {
      staleGet: true,
      initialTitles: [[7, "Conversa A"], [8, "Conversa B"]],
    });
    page.on("dialog", (d) => d.accept()); // confirm() do excluir
    await page.goto("/");
    await expect(page.getByText("Conversa A")).toBeVisible();

    // Renomeia A (PATCH commita no servidor, mas o GET continua devolvendo "Conversa A").
    await page.getByRole("button", { name: "Renomear conversa: Conversa A" }).click();
    const input = page.getByRole("textbox", { name: "Novo título da conversa" });
    await input.fill("A renomeada");
    await input.press("Enter");
    await expect(page.getByText("A renomeada")).toBeVisible();
    expect(patchCalls).toHaveLength(1);

    // Excluir B dispara um fetchHistory concorrente (GET obsoleto: A ainda "Conversa A").
    await page.getByRole("button", { name: "Excluir conversa: Conversa B" }).click();
    await expect(page.getByText("Conversa B")).toHaveCount(0); // B some (membership atual)
    // O overlay de pendentes mantém "A renomeada" — sem ele, reverteria p/ "Conversa A".
    await expect(page.getByText("A renomeada")).toBeVisible();
    await expect(page.getByText("Conversa A")).toHaveCount(0);
  });

  test("título muito longo trunca e NÃO corta os botões de renomear/excluir", async ({ page }) => {
    // Regressão do bug do viewport do Radix ScrollArea (display: table dimensiona
    // pelo conteúdo): um título longo alargava a linha além da sidebar, o truncate
    // nunca agia e o lápis/lixeira saíam cortados pela borda direita.
    const longo =
      "Negociação de Taxa Administrativa FAI com condições especiais para projetos " +
      "de extensão de longa duração e múltiplos financiadores envolvidos";
    await mockApi(page, { initialTitles: [[7, longo], [8, "Curta"]] });
    await page.goto("/");
    await expect(page.getByText("Curta")).toBeVisible();

    // Dois <aside> na página (sidebar + painel de fontes); a sidebar é o primeiro.
    const aside = page.locator("aside").first();
    const asideBox = await aside.boundingBox();
    expect(asideBox).not.toBeNull();

    for (const name of [`Renomear conversa: ${longo}`, `Excluir conversa: ${longo}`]) {
      const btn = page.getByRole("button", { name });
      await expect(btn).toBeVisible();
      const box = await btn.boundingBox();
      expect(box).not.toBeNull();
      // O botão inteiro precisa caber DENTRO da sidebar (não cortado à direita).
      expect(box!.x + box!.width).toBeLessThanOrEqual(asideBox!.x + asideBox!.width + 1);
    }

    // E o título de fato truncou (conteúdo maior que a área visível).
    const truncated = await page
      .getByRole("button", { name: longo, exact: false })
      .first()
      .evaluate((el) => el.scrollWidth > el.clientWidth);
    expect(truncated).toBe(true);
  });
});
