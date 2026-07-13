import { test, expect, Page, Route } from "@playwright/test";

/**
 * Testes de UI da tela de boas-vindas (WelcomeScreen) do ChatWindow.
 *
 * Diferente do manual-qa.spec.ts (que dirige o modelo real), aqui o backend é
 * TODO mockado no nível de rede — os testes validam só o comportamento da UI e
 * rodam em segundos, sem stack no ar além do frontend.
 *
 * Rodar: BASE_URL=http://localhost:3100 npx playwright test tests/welcome.spec.ts
 */

// Espelho VERBATIM das sugestões do componente (SUGGESTED_QUESTIONS em
// ChatWindow.tsx). Se alguém alterar lá e não aqui, o teste 1 falha — de
// propósito: as perguntas são calibradas pela bateria de consistência e
// não devem mudar por acidente.
const SUGGESTED = [
  "Qual é o limite financeiro para a contratação direta de serviços e compras com recursos públicos e como evitar o fracionamento de despesa?",
  "Quais as limitações para a contratação de profissionais autônomos (Pessoa Física)?",
  "Quais os prazos e trâmites para obras de engenharia nos campi da UFSCar?",
];

const ANSWER = "O limite é de R$ 17.600,00 conforme o manual.";
const SOURCES = ["- Manual do Coordenador.pdf (pág. 12)"];

// Corpo SSE de uma resposta completa do /chat/stream (2 chunks + done),
// no mesmo formato que o backend emite.
function sseBody(): string {
  return [
    `data: ${JSON.stringify({ content: ANSWER.slice(0, 20) })}`,
    "",
    `data: ${JSON.stringify({ content: ANSWER.slice(20) })}`,
    "",
    `data: ${JSON.stringify({ done: true, conversation_id: 1, sources: SOURCES, gen_time: 1.23, usage: 100 })}`,
    "",
    "",
  ].join("\n");
}

interface MockOptions {
  conversations?: Array<{ id: number; title: string }>;
  messages?: Array<{ role: string; content: string; metadata?: Record<string, unknown> }>;
  // Atrasa o 1º /chat/stream (deixa o stream "em voo" p/ testar troca de conversa no meio).
  slowFirstStreamMs?: number;
  // O 1º GET de mensagens falha com 500 (testa o estado de erro com retry).
  failFirstMessagesLoad?: boolean;
}

// Intercepta TODA a API (tanto same-origin /api/v1 quanto http://localhost:8000/api/v1,
// conforme NEXT_PUBLIC_API_URL) e registra os corpos enviados ao /chat/stream.
async function mockApi(
  page: Page,
  opts: MockOptions = {}
): Promise<{ askedQuestions: string[]; askedBodies: Array<Record<string, unknown>> }> {
  const askedQuestions: string[] = [];
  const askedBodies: Array<Record<string, unknown>> = [];
  let streamCalls = 0;
  let messagesCalls = 0;

  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith("/status")) {
      return route.fulfill({ json: { lightrag: { status: "online" } } });
    }
    if (path.endsWith("/chat/stream")) {
      const body = route.request().postDataJSON();
      askedQuestions.push(body?.question ?? "");
      askedBodies.push(body ?? {});
      streamCalls++;
      if (streamCalls === 1 && opts.slowFirstStreamMs) {
        await new Promise((r) => setTimeout(r, opts.slowFirstStreamMs));
      }
      // O cliente pode ter ABORTADO o fetch durante o atraso (troca de conversa) —
      // nesse caso o fulfill lança e engolimos: é exatamente o cenário sob teste.
      return route
        .fulfill({ status: 200, contentType: "text/event-stream", body: sseBody() })
        .catch(() => {});
    }
    if (/\/history\/\d+\/messages$/.test(path)) {
      messagesCalls++;
      if (messagesCalls === 1 && opts.failFirstMessagesLoad) {
        return route.fulfill({ status: 500, json: { detail: "erro simulado" } });
      }
      return route.fulfill({ json: opts.messages ?? [] });
    }
    if (/\/history\/?$/.test(path)) {
      return route.fulfill({ json: opts.conversations ?? [] });
    }
    return route.fulfill({ status: 404, json: { detail: "mock: rota não mapeada" } });
  });

  return { askedQuestions, askedBodies };
}

test.describe("Tela de boas-vindas", () => {
  test("aparece em conversa nova, com saudação e as 3 sugestões verbatim", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    const welcome = page.getByTestId("welcome-message");
    await expect(welcome).toBeVisible();
    await expect(welcome.getByRole("heading", { name: /Olá! Eu sou a Lina/ })).toBeVisible();
    await expect(welcome.getByText("Experimente perguntar")).toBeVisible();

    const chips = page.getByTestId("suggestion-chip");
    await expect(chips).toHaveCount(SUGGESTED.length);
    for (let i = 0; i < SUGGESTED.length; i++) {
      await expect(chips.nth(i)).toHaveText(SUGGESTED[i]);
      await expect(chips.nth(i)).toBeEnabled();
    }
  });

  test("chip envia a pergunta VERBATIM ao backend e a tela some", async ({ page }) => {
    const { askedQuestions } = await mockApi(page);
    await page.goto("/");

    await page.getByTestId("suggestion-chip").first().click();

    // Tela some imediatamente; a pergunta vira mensagem do usuário na conversa.
    await expect(page.getByTestId("welcome-message")).toHaveCount(0);
    await expect(page.getByTestId("user-content")).toHaveText(SUGGESTED[0]);

    // Resposta mockada conclui (evento done) e as fontes viram chips.
    await expect(page.getByTestId("message-done")).toBeVisible();
    await expect(page.getByTestId("assistant-content")).toContainText("R$ 17.600,00");
    await expect(page.getByTestId("source-chip").first()).toContainText("Manual do Coordenador.pdf");

    // O corpo da requisição levou a sugestão sem nenhum encurtamento.
    expect(askedQuestions).toEqual([SUGGESTED[0]]);
  });

  test("clicar numa sugestão NÃO descarta rascunho digitado no input", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    const input = page.getByTestId("chat-input");
    await input.fill("rascunho que eu ainda estava escrevendo");
    await page.getByTestId("suggestion-chip").first().click();

    await expect(page.getByTestId("message-done")).toBeVisible();
    await expect(input).toHaveValue("rascunho que eu ainda estava escrevendo");
  });

  test("lixeira (nova conversa) traz a tela de boas-vindas de volta", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await page.getByTestId("suggestion-chip").first().click();
    await expect(page.getByTestId("message-done")).toBeVisible();

    await page.getByRole("button", { name: "Limpar conversa" }).click();
    await expect(page.getByTestId("welcome-message")).toBeVisible();
    await expect(page.getByTestId("user-content")).toHaveCount(0);
  });

  test("avatar da Lina abre o modal 'Sobre a Lina'", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await page.getByTestId("welcome-message").getByRole("button", { name: "Sobre a Lina" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Assistente Virtual · FAI-UFSCar")).toBeVisible();
  });

  test("NÃO aparece com conversa selecionada; volta ao desselecionar", async ({ page }) => {
    await mockApi(page, {
      conversations: [{ id: 7, title: "Conversa antiga" }],
      messages: [
        { role: "user", content: "pergunta antiga" },
        { role: "assistant", content: "resposta antiga", metadata: { sources: SOURCES, gen_time: 2.5 } },
      ],
    });
    await page.goto("/");
    await expect(page.getByTestId("welcome-message")).toBeVisible();

    // Seleciona a conversa na sidebar: boas-vindas some, mensagens carregam.
    await page.getByRole("button", { name: "Conversa antiga", exact: true }).click();
    await expect(page.getByTestId("welcome-message")).toHaveCount(0);
    await expect(page.getByTestId("user-content")).toHaveText("pergunta antiga");
    await expect(page.getByTestId("assistant-content")).toContainText("resposta antiga");

    // A lixeira desseleciona (onNewChat) e a tela de boas-vindas reaparece.
    await page.getByRole("button", { name: "Limpar conversa" }).click();
    await expect(page.getByTestId("welcome-message")).toBeVisible();
  });

  test("'Nova Conversa' no meio do stream NÃO contamina a conversa antiga", async ({ page }) => {
    const { askedBodies } = await mockApi(page, {
      conversations: [{ id: 7, title: "Conversa antiga" }],
      messages: [
        { role: "user", content: "pergunta antiga" },
        { role: "assistant", content: "resposta antiga", metadata: { gen_time: 2.5 } },
      ],
      slowFirstStreamMs: 4000,
    });
    await page.goto("/");

    // Entra na conversa 7 e manda um follow-up (o stream fica pendurado 4s).
    await page.getByRole("button", { name: "Conversa antiga", exact: true }).click();
    await expect(page.getByTestId("assistant-content")).toContainText("resposta antiga");
    await page.getByTestId("chat-input").fill("follow-up na conversa 7");
    await page.getByTestId("chat-send").click();

    // No meio do stream, troca para conversa nova: o stream em voo deve ser abortado
    // e a tela de boas-vindas aparecer de fato limpa.
    await page.getByRole("button", { name: "Nova Conversa" }).click();
    await expect(page.getByTestId("welcome-message")).toBeVisible();

    // Dá tempo do stream obsoleto "chegar" — abortado, não pode restaurar o id antigo.
    await page.waitForTimeout(4500);
    await expect(page.getByTestId("welcome-message")).toBeVisible();

    // A sugestão clicada agora deve abrir conversa NOVA (conversation_id null),
    // não anexar à conversa 7.
    await page.getByTestId("suggestion-chip").first().click();
    await expect(page.getByTestId("message-done")).toBeVisible();
    expect(askedBodies).toHaveLength(2);
    expect(askedBodies[0].conversation_id).toBe(7);
    expect(askedBodies[1].conversation_id).toBeNull();
  });

  test("falha ao carregar conversa mostra erro inline com 'Tentar novamente'", async ({ page }) => {
    await mockApi(page, {
      conversations: [{ id: 7, title: "Conversa antiga" }],
      messages: [{ role: "user", content: "pergunta antiga" }],
      failFirstMessagesLoad: true,
    });
    await page.goto("/");

    await page.getByRole("button", { name: "Conversa antiga", exact: true }).click();

    // Nem tela em branco, nem boas-vindas fingindo conversa nova: erro com retry.
    const errorBox = page.getByTestId("conversation-load-error");
    await expect(errorBox).toBeVisible();
    await expect(page.getByTestId("welcome-message")).toHaveCount(0);

    // O retry refaz o fetch (o 2º GET responde ok) e a conversa carrega.
    await errorBox.getByRole("button", { name: "Tentar novamente" }).click();
    await expect(page.getByTestId("user-content")).toHaveText("pergunta antiga");
    await expect(errorBox).toHaveCount(0);
  });

  test("setinha 'ir para a última mensagem' não aparece sobre a tela de boas-vindas", async ({ page }) => {
    await mockApi(page);
    // Janela baixa: o conteúdo da welcome excede o contêiner e cria scroll.
    await page.setViewportSize({ width: 900, height: 380 });
    await page.goto("/");
    await expect(page.getByTestId("welcome-message")).toBeVisible();

    // Rola dentro da área de mensagens para longe do fim (dispara handleMessagesScroll).
    await page.evaluate(() => {
      const el = document.querySelector('[data-testid="welcome-message"]')?.parentElement;
      if (el) {
        el.scrollTop = el.scrollHeight; // fim
        el.scrollTop = 0;               // volta ao topo (fica a >160px do fim)
      }
    });
    await page.waitForTimeout(300);
    // Sem mensagens não há sentinela (o clique seria um no-op) — a seta não deve existir.
    await expect(page.getByRole("button", { name: "Ir para a última mensagem" })).toHaveCount(0);
  });
});
