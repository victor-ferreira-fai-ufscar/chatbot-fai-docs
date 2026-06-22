# Avaliação de precisão — Chatbot do Manual do Coordenador

Verifica se o chatbot responde de forma **fundamentada no manual**, **sem alucinar** e
**citando a fonte/página correta**, usando as perguntas reais das áreas (TI, Projetos,
Adm. Financeiro, Engenharia, etc.).

## Arquivos
- `eval_questions.json` — conjunto **congelado** de 53 perguntas com gabarito humano,
  extraído de `docs/perguntas/*.docx`. (regenerar só se as perguntas mudarem)
- `eval_manual_qa.py` — harness (coleta → verificações duras → placar de correção).
- `.last_run.json` — saída da última coleta (NÃO versionado).

## Como rodar
Pré-requisitos: stack no ar (`docker compose up -d`); roda no host (só stdlib).

```bash
# 1) coleta as respostas do chatbot ao vivo (lento, ~20 min)
python3 backend/eval/eval_manual_qa.py --collect

# 2) VERIFICAÇÕES DURAS (rápido) — é o "teste": exit code != 0 se houver violação
python3 backend/eval/eval_manual_qa.py --check

# 3) placar de correção vs gabarito (juiz = gpt-oss local via Ollama)
python3 backend/eval/eval_manual_qa.py --judge

# tudo de uma vez
python3 backend/eval/eval_manual_qa.py --all
```

## O que as verificações DURAS pegam (anti-alucinação)
Falham o teste (exit ≠ 0):
- **fonte_fabricada** — citou um arquivo que não é um manual conhecido (ex.: inventou
  `Manual_Coordenadores.pdf` ou alterou o nome real).
- **pagina_invalida** — citou página fora de `[1, 73]`.
- **ref_legal_fabricada** — citou Lei/Decreto/Resolução/Portaria cujo número **não existe**
  no texto indexado do manual (ou seja, citou norma de cabeça).

Reportado (não falha): resposta factual longa **sem nenhuma fonte**.

## Observações
- "100% de acerto" num LLM não é garantível; o objetivo aqui é **medir e travar regressões**.
  As verificações duras garantem que ele não fabrica fonte/lei; o placar mede a correção.
- Perguntas específicas de **financiadores (FINEP/FAPESP/CNPq)** geralmente **não estão**
  neste manual — abster-se ("não consta") é o comportamento CORRETO nessas, e o juiz
  classifica como `abstencao_ok`.
- O texto do manual usado nas checagens vem de `lightrag/data/rag_storage/kv_store_full_docs.json`
  (o que o bot realmente indexa).
