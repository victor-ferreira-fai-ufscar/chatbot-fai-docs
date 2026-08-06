import { Page, Route } from "@playwright/test";

/**
 * Mock de rede compartilhado dos specs NOVOS (desktop-baseline e mobile-responsive).
 *
 * É um superset do padrão de tests/welcome.spec.ts (SSE montado à mão, history CRUD,
 * espiões de corpo enviado). Os 3 specs antigos (welcome/rename/export) mantêm seus
 * mocks locais DE PROPÓSITO: eles são a prova de não-regressão desta iniciativa e
 * não devem ser tocados. Unificação fica como limpeza posterior opcional.
 */

export const DEFAULT_ANSWER = "O limite é de R$ 17.600,00 conforme o manual.";

// ≤5 fontes: NÃO aciona o ramo de agrupamento de groupSourceLines (ChatWindow),
// mantendo o baseline imune à compressão de intervalos planejada para o mobile.
export const DEFAULT_SOURCES = [
  "- Manual do Coordenador.pdf (pág. 12 · 96%)",
  "- Manual do Coordenador.pdf (pág. 26 · 88%)",
];

// Texto fixo devolvido por /documents/page-text (card de fonte do painel).
export const PAGE_TEXT =
  "Trecho determinístico do manual para o card de fonte. O limite para contratação " +
  "direta é definido em norma específica e deve ser observado pelo coordenador.";

export interface MockMessage {
  role: string;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface MockApiOptions {
  conversations?: Array<{ id: number; title: string }>;
  messages?: MockMessage[];
  /** Resposta do /chat/stream (default: DEFAULT_ANSWER). */
  answer?: string;
  /** Fontes emitidas no evento done do stream (default: DEFAULT_SOURCES). */
  sources?: string[];
  /** Conversa devolvida por GET /shared/:token (página pública). Sem isso, 404. */
  shared?: { title: string; messages: MockMessage[] };
}

export interface MockApiSpies {
  askedQuestions: string[];
  askedBodies: Array<Record<string, unknown>>;
  shareCalls: string[];
}

// Corpo SSE de uma resposta completa (2 chunks + done), no formato do backend.
function sseBody(answer: string, sources: string[]): string {
  const mid = Math.ceil(answer.length / 2);
  return [
    `data: ${JSON.stringify({ content: answer.slice(0, mid) })}`,
    "",
    `data: ${JSON.stringify({ content: answer.slice(mid) })}`,
    "",
    `data: ${JSON.stringify({ done: true, conversation_id: 1, sources, gen_time: 1.23, usage: 100 })}`,
    "",
    "",
  ].join("\n");
}

// Intercepta TODA a API (same-origin /api/v1 e http://localhost:8000/api/v1).
// Rota não mapeada devolve 404 ruidoso — falha visível em vez de silenciosa.
export async function mockApi(page: Page, opts: MockApiOptions = {}): Promise<MockApiSpies> {
  const spies: MockApiSpies = { askedQuestions: [], askedBodies: [], shareCalls: [] };
  const answer = opts.answer ?? DEFAULT_ANSWER;
  const sources = opts.sources ?? DEFAULT_SOURCES;

  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path.endsWith("/status")) {
      return route.fulfill({ json: { lightrag: { status: "online" } } });
    }
    if (path.endsWith("/chat/stream")) {
      const body = route.request().postDataJSON();
      spies.askedQuestions.push(body?.question ?? "");
      spies.askedBodies.push(body ?? {});
      // O cliente pode ter abortado o fetch — engolimos como nos specs antigos.
      return route
        .fulfill({ status: 200, contentType: "text/event-stream", body: sseBody(answer, sources) })
        .catch(() => {});
    }
    if (path.endsWith("/documents/page-text")) {
      return route.fulfill({ json: { text: PAGE_TEXT } });
    }
    if (path.endsWith("/documents/download-url")) {
      return route.fulfill({ json: { signed_url: "https://example.invalid/manual.pdf" } });
    }
    if (/\/shared\/[^/]+$/.test(path)) {
      if (!opts.shared) return route.fulfill({ status: 404, json: { detail: "não encontrado" } });
      return route.fulfill({ json: opts.shared });
    }
    if (/\/history\/\d+\/share$/.test(path) && method === "POST") {
      spies.shareCalls.push(path);
      return route.fulfill({ json: { path: "/shared/tok-mock-123" } });
    }
    if (/\/history\/\d+\/export\.pdf$/.test(path)) {
      return route.fulfill({
        status: 200,
        contentType: "application/pdf",
        headers: { "content-disposition": 'attachment; filename="conversa-teste.pdf"' },
        body: "%PDF-1.4\n%mock\n%%EOF",
      });
    }
    if (/\/history\/\d+\/messages$/.test(path)) {
      return route.fulfill({ json: opts.messages ?? [] });
    }
    if (/\/history\/\d+$/.test(path) && (method === "PATCH" || method === "DELETE")) {
      return route.fulfill({ json: { ok: true } });
    }
    if (/\/history\/?$/.test(path)) {
      if (method === "DELETE") return route.fulfill({ json: { ok: true } });
      return route.fulfill({ json: opts.conversations ?? [] });
    }
    return route.fulfill({ status: 404, json: { detail: "mock: rota não mapeada" } });
  });

  return spies;
}
