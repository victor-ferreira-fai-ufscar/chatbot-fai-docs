---
name: gerar_documento_pdf
description: "Gera um documento PDF (relatorio, declaracao, comunicado) a partir de conteudo em Markdown e devolve um link de download. Use quando pedirem um PDF, relatorio ou documento formatado."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    titulo:
      type: string
      description: "Titulo do documento (vira o nome do arquivo e o cabecalho da pagina)."
    conteudo_markdown:
      type: string
      description: "Corpo do documento em Markdown (titulos ##, listas, **negrito**, tabelas). NAO repita o titulo aqui."
    rodape:
      type: string
      description: "Texto opcional do rodape (ex.: orgao, data). O numero da pagina e adicionado automaticamente."
  required: [titulo, conteudo_markdown]
---

# gerar_documento_pdf

Monta um PDF institucional a partir de conteudo em Markdown (convertido para HTML
e renderizado com CSS pelo WeasyPrint), salva no repositorio e devolve um link de
download. Bom para "gere um relatorio em PDF", "monte uma declaracao", "exporta
isso como documento".

## Como usar
- O conteudo factual (`conteudo_markdown`) normalmente vem de uma consulta anterior:
  chame `consultar_base_conhecimento` primeiro e so entao gere o PDF. NAO invente
  dados que nao constam nos manuais.
- Escreva o corpo em Markdown: use `##`/`###` para secoes, `-`/`1.` para listas,
  `**negrito**`, `_italico_` e tabelas com `|`. NAO inclua o titulo no corpo (ele
  ja entra como cabecalho a partir de `titulo`).
- `rodape` e opcional; o numero da pagina e sempre adicionado.

## Entrega
O link de download e gerado pelo sistema e anexado automaticamente a resposta
(chip de download). Voce NAO precisa (e nao deve) escrever a URL; apenas confirme
de forma breve que o documento foi gerado.
