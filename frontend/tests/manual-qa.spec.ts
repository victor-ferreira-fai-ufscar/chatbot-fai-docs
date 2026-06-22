import { test, expect } from "@playwright/test";
import questions from "./data/questions.json";
import { evaluateAnswer } from "./helpers";

interface Q {
  id: string;
  category: string;
  question: string;
  reference: string;
}

// Roda todas as 53 perguntas por padrão; E2E_LIMIT=N roda só as N primeiras (iteração rápida).
const ALL = questions as Q[];
const LIMIT = process.env.E2E_LIMIT ? parseInt(process.env.E2E_LIMIT, 10) : ALL.length;
const SUBSET = ALL.slice(0, LIMIT);

test.describe("Precisão do chatbot vs Manual do Coordenador", () => {
  for (const q of SUBSET) {
    test(`${q.id} — ${q.question.slice(0, 70)}`, async ({ page }, testInfo) => {
      await page.goto("/");

      const input = page.getByTestId("chat-input");
      await input.waitFor({ state: "visible" });
      await input.fill(q.question);
      await page.getByTestId("chat-send").click();

      // A resposta concluiu quando o "Resposta gerada em ..." (evento done) aparece.
      await page.getByTestId("message-done").last().waitFor({ state: "visible", timeout: 130_000 });

      const answer = (await page.getByTestId("assistant-content").last().innerText()).trim();
      const chips = await page.getByTestId("source-chip").allInnerTexts();
      const checks = evaluateAnswer(answer, chips);

      // Anexa tudo ao relatório HTML para revisão humana (pergunta, gabarito, resposta, fontes, checks).
      await testInfo.attach(`${q.id}.json`, {
        body: JSON.stringify({ ...q, answer, chips, checks }, null, 2),
        contentType: "application/json",
      });

      expect(answer.length, "a resposta não pode ser vazia").toBeGreaterThan(0);
      expect(answer.startsWith("Erro"), "a resposta não pode ser um erro").toBeFalsy();

      // === VERIFICAÇÕES DURAS (anti-alucinação / citação, com base no manual) ===
      expect(checks.fabricatedSources, "citou arquivo de fonte que não é um manual conhecido").toEqual([]);
      expect(checks.invalidPages, "citou página fora do intervalo do manual [1,73]").toEqual([]);
      expect(checks.fabricatedLaws, "citou Lei/Decreto/Resolução cujo número não existe no manual").toEqual([]);

      // === MOLE (apenas alerta, não falha): resposta factual longa sem nenhuma fonte ===
      if (!checks.abstention && answer.length > 200 && !checks.grounded) {
        testInfo.annotations.push({
          type: "warning",
          description: `${q.id}: resposta factual sem fonte citada`,
        });
      }
    });
  }
});
