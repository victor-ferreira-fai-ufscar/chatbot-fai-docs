---
name: gerar_planilha
description: "Gera uma planilha (.xlsx por padrao, ou .csv) a partir de dados estruturados e devolve um link de download. Use quando o usuario pedir tabela, planilha ou exportacao de dados."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    titulo:
      type: string
      description: "Titulo da planilha (vira o nome do arquivo e o titulo da aba)."
    colunas:
      type: array
      items: { type: string }
      description: "Nomes das colunas (cabecalho), na ordem desejada."
    linhas:
      type: array
      items:
        type: array
        items: { type: string }
      description: "Linhas de dados; cada linha e uma lista de valores na MESMA ordem das colunas."
    formato:
      type: string
      enum: [xlsx, csv]
      description: "Formato do arquivo. Padrao: xlsx."
  required: [titulo, colunas, linhas]
---

# gerar_planilha

Monta uma planilha a partir de dados estruturados, salva no repositorio e devolve
um link de download. Bom para "monte uma tabela com X", "exporta isso em planilha".

## Como usar
- Os dados (`linhas`) normalmente vem de uma consulta anterior: chame
  `consultar_base_conhecimento` primeiro, extraia os valores e so entao gere a
  planilha. NAO invente dados que nao constam nos manuais.
- `colunas` e cada `linha` devem ter o mesmo numero de elementos, na mesma ordem.
- Use valores como texto (strings); numeros tambem podem ir como string.
- `formato`: `xlsx` (padrao) para Excel; `csv` quando pedirem CSV.

## Entrega
O link de download e gerado pelo sistema e anexado automaticamente a resposta
(chip de download). Voce NAO precisa (e nao deve) escrever a URL; apenas confirme
de forma breve que a planilha foi gerada.
