---
name: entregar_documento
description: "Entrega ao usuario um documento JA EXISTENTE no repositorio (manuais e arquivos indexados), gerando um link de download. Use quando pedirem para RECEBER, BAIXAR ou ENVIAR um manual/documento existente (inclusive referencias como 'esse documento', 'o anterior'). NAO use para criar arquivos novos (use gerar_planilha/gerar_documento_pdf)."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    referencia:
      type: string
      description: "Como o usuario se referiu ao documento: nome ('manual do coordenador') ou referencia de contexto ('esse documento', 'o que voce citou', 'o anterior')."
  required: [referencia]
---

# entregar_documento

Entrega um arquivo que JA EXISTE no repositorio (ex.: manuais institucionais
indexados). Um resolvedor por IA identifica QUAL documento o usuario quer — a
partir da `referencia`, do historico da conversa e das fontes citadas nesta
mesma interacao — e o sistema gera um link de download assinado.

## Como usar
- Esta skill NAO cria arquivos novos. Para gerar uma planilha use `gerar_planilha`;
  para gerar um PDF use `gerar_documento_pdf`.
- `referencia` pode ser o nome ("manual do coordenador") ou uma referencia de
  contexto ("me envia esse documento", "manda o anterior"). O resolvedor usa o
  historico e as fontes ja citadas para desambiguar.
- Quando a referencia for ambigua, a skill devolve uma lista de candidatos: nesse
  caso, PERGUNTE ao usuario qual deles ele quer e chame a skill de novo com o nome.

## Entrega
O link de download e gerado pelo sistema e anexado automaticamente a resposta
(chip de download). Voce NAO precisa (e nao deve) escrever a URL; apenas confirme
de forma breve qual documento foi localizado.
