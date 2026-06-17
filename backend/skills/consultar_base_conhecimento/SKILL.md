---
name: consultar_base_conhecimento
description: "Consulta os manuais e documentos institucionais da FAI (base de conhecimento via LightRAG). Use SEMPRE que a pergunta exigir informacao factual sobre processos, normas, prazos, valores, contatos ou conteudo de manuais. NAO use para conversa social nem para perguntas sobre a propria Lina."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    consulta:
      type: string
      description: "A pergunta/termo a buscar, reescrita de forma objetiva para maximizar a recuperacao no grafo (mantenha as palavras-chave relevantes)."
    modo:
      type: string
      enum: [mix, hybrid, local, global]
      description: "Modo de busca do grafo. Padrao: mix."
  required: [consulta]
---

# consultar_base_conhecimento

Ferramenta-nucleo do agente: recupera trechos dos manuais institucionais da FAI
(via LightRAG) e devolve um texto fundamentado, com as fontes citadas.

## Quando usar
- Toda pergunta factual sobre processos, normas, prazos, valores, contatos ou
  conteudo dos manuais.
- ANTES de gerar planilha/PDF a partir de dados dos manuais: consulte aqui primeiro
  e use o resultado para preencher o artefato.

## Quando NAO usar
- Conversa social (saudacao, agradecimento, despedida).
- Perguntas sobre quem e a Lina / o que ela faz.

## Ancoragem (regra maxima)
Responda EXCLUSIVAMENTE com base no que esta ferramenta retornar. Se a informacao
nao estiver no resultado, diga que nao consta nos manuais (protocolo de negativa);
nunca complemente com conhecimento externo nem invente dados (leis, numeros, prazos).

## Parametros
- `consulta`: reescreva a pergunta do usuario de forma objetiva, preservando os
  termos-chave (valores, nomes de processos, setores) para maximizar a recuperacao.
- `modo`: use `mix` por padrao. `local` foca em entidades especificas; `global` em
  panorama/relacoes; `hybrid` combina os dois.

As fontes recuperadas sao anexadas automaticamente a resposta final (chips de
"Fontes Pesquisadas"); voce nao precisa lista-las manualmente nem inventar URLs.
