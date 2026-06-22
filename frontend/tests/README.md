# Testes E2E (Playwright) — precisão do chatbot

Dirige a **UI real** do chat (não a API): para cada pergunta de `docs/perguntas/`,
digita no campo, envia, espera a resposta e verifica se ela está fundamentada no
**Manual do Coordenador**.

## Pré-requisitos
1. Stack no ar: `docker compose up -d` (frontend em `:3000`, backend em `:8000`).
2. Browser do Playwright (uma vez):
   ```bash
   cd frontend
   npx playwright install --with-deps chromium
   ```
   > `--with-deps` instala as libs de sistema do Chromium (precisa de sudo na 1ª vez).

## Rodar
```bash
cd frontend
npm run test:e2e                 # todas as 53 perguntas (~25-40 min; backend serializa)
E2E_LIMIT=5 npm run test:e2e     # só as 5 primeiras (iteração rápida)
npm run test:e2e:report          # abre o relatório HTML (resposta + gabarito + checks por pergunta)
BASE_URL=http://outro-host:3000 npm run test:e2e   # apontar p/ outro ambiente
```

## O que cada teste verifica (com base no manual)
**Falham o teste (anti-alucinação / citação):**
- resposta não-vazia e não-erro;
- **fonte real**: todo arquivo citado é um manual conhecido (não inventa nome);
- **página válida**: páginas citadas dentro de `[1, 73]`;
- **sem lei fabricada**: todo nº de Lei/Decreto/Resolução citado existe no manual
  (casa por número-base, então CLT/ISS/Código Civil que o manual referencia passam).

**Alerta (não falha):** resposta factual longa sem nenhuma fonte (a menos que seja abstenção).

Cada teste **anexa ao relatório** a pergunta, o gabarito humano, a resposta do bot, as
fontes e o resultado das checagens — então o relatório HTML serve para **revisão manual**
de "a resposta está certa?" pergunta a pergunta.

## Notas
- Serializado (`workers: 1`): o backend processa 1 requisição por vez (`MAX_ASYNC=1`).
- Selectores estáveis via `data-testid` no `ChatWindow` (`chat-input`, `chat-send`,
  `assistant-content`, `message-done`, `source-chip`).
- A allowlist de leis do manual está em `tests/data/manual-law-bases.json` (regenere se o
  manual mudar). As perguntas em `tests/data/questions.json` (espelham `backend/eval/`).
- Correção **semântica** vs gabarito (juiz LLM) fica no harness Python:
  `python3 backend/eval/eval_manual_qa.py --judge`. Este E2E cobre a UI + fundamentação.
