---
name: consultar_base_conhecimento
description: "FERRAMENTA PADRAO do agente: consulta os manuais institucionais da FAI (base de conhecimento via LightRAG). Chame ANTES de responder QUALQUER pergunta factual sobre a FAI — processos, normas, prazos, valores, contatos, sistemas ou conteudo de manuais — mesmo que voce ache que sabe a resposta. Reescreva a consulta no vocabulario formal dos manuais. NAO use apenas em conversa puramente social ou sobre a propria Lina."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    consulta:
      type: string
      description: "A pergunta reescrita em linguagem FORMAL de manual institucional: troque termos coloquiais pelo termo oficial provavel (ex.: 'numerozinho vermelho no topo da tela' -> 'icone de notificacoes'; 'grana do projeto' -> 'recursos financeiros do projeto'). Preserve as palavras-chave (valores, nomes de processos, formularios, setores) e resolva pronomes usando o historico (nunca envie 'isso'/'ele' na consulta). Compras/contratacoes/limites/orcamentos tem regras DIFERENTES por origem do recurso: se o usuario nao especificou a origem, inclua 'recursos publicos e privados' na consulta."
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
- Perguntas sobre o que a FAI faz, como funciona, quais setores existem, quem contatar, etc.
- Sobre Instituições Apoiadas: quais sao, como funcionam, quem contatar, etc. Pois pode informar o que consta no manual referente a cada Instituicao Apoiadora, mas NAO pode inventar dados (ex.: "qual o telefone do fulano da Instituicao X?").

## Quando NAO usar
- Conversa social (saudacao, agradecimento, despedida).
- Perguntas sobre quem e a Lina / o que ela faz.
- Perguntas fora do escopo da FAI (ex.: "qual a capital da França?").

## Ancoragem (regra maxima)
Responda EXCLUSIVAMENTE com base no que esta ferramenta retornar, não resuma ou diminua o conteudo.Se a informacao nao estiver no resultado, diga que nao consta nos manuais (protocolo de negativa);
nunca complemente com conhecimento externo nem invente dados (leis, numeros, prazos, termos e Siglas).

## Parametros
- `consulta`: reescreva a pergunta do usuario de forma objetiva, preservando os
  termos-chave (valores, nomes de processos, setores) para maximizar a recuperacao.
- `modo`: use `mix` por padrao. `local` foca em entidades especificas; `global` em
  panorama/relacoes; `hybrid` combina os dois.

## Como escrever a consulta
- Reescreva em vocabulario de MANUAL: formal, sem girias ("como pego o
  dinheiro" -> "procedimento para solicitacao de recursos financeiros do projeto").
- Troque descricoes coloquiais/sintomaticas pelo termo oficial provavel
  ("numerozinho vermelho no topo da tela" -> "icone de notificacoes";
  "a aba fechou e perdi tudo" -> "rascunho salvo do formulario").
- Mantenha os termos-chave da pergunta (nomes de processos, sistemas, formularios,
  valores, setores).
- Compras, contratacoes, limites e orcamentos costumam ter regras DIFERENTES por
  origem do recurso: se o usuario nao especificou a origem, inclua na consulta os
  termos "recursos publicos" e "recursos privados" (a resposta deve cobrir os dois
  regimes quando eles diferem).


## Segunda tentativa OBRIGATORIA
- Se o resultado vier VAZIO ou disser que o assunto nao consta, NAO desista ainda:
  reformule a `consulta` (sinonimos, termo oficial provavel, ou troque `modo` para
  `hybrid`) e chame esta skill UMA segunda vez.
- So aplique o protocolo de negativa (token-sentinela) depois de DUAS tentativas
  sem resultado.

As fontes recuperadas sao anexadas automaticamente a resposta final (chips de
"Fontes Pesquisadas"); voce nao precisa lista-las manualmente nem inventar URLs.
