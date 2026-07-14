# Bateria de Testes — Manual do Sistema Área de Coordenadores (how-to da plataforma)

> **Data:** 2026-07-14 · **Perguntas:** 15 (respondíveis SOMENTE por este manual)
> **Ground-truth:** `docs/manual_sistema_area_page_marked.txt` (marcadores `[PÁGINA N]` = página real do PDF)
> **Config do chat:** modo agêntico ON (gemma4:12b) · LightRAG `mix` (gpt-oss think=high) · mitigações multi-manual ativas (regra 4.5, guard de grounding, validação citação×recuperado)
> **Status:** respostas preenchidas (15/15)

As *páginas de referência* e a *resposta esperada* vêm do ground-truth e servem para conferir manualmente a qualidade de cada resposta (a fonte citada deve apontar para essas páginas do `Manual do Sistema Área Coordenadores.pdf`).

---

## SIST-01 — Login e Senha

**Pergunta:** Esqueci minha senha da Área de Coordenadores. Como faço para recuperar o acesso?

**Páginas de referência (ground-truth):** 4

**Resposta esperada (fatos-chave):** Inserir a identificação (e-mail ou CPF) no campo login e clicar em 'Esqueci a Senha'; uma mensagem automática é enviada para o e-mail cadastrado.

**Resposta do chatbot** *(latência 135.0s · skills: consultar_base_conhecimento, verificando_fontes, consultar_base_conhecimento)*:

Para recuperar sua senha na **Área de Coordenadores**, você deve seguir o procedimento detalhado no manual do sistema:

1.  **Acesse a página de login**: Acesse o endereço `https://sistemas.fai.ufscar.br/coordenadores`.
2.  **Solicite a recuperação**: Na tela de autenticação, clique no link **"Esqueci a Senha"**.
3.  **Identificação**: Informe seu e-mail ou CPF cadastrado no campo indicado (e complete o captcha "Não sou um robô", se solicitado).
4.  **Envio do pedido**: Clique em **Enviar**. Uma mensagem automática será enviada para o seu e-mail registrado.
5.  **Redefinição**: Acesse o e-mail recebido, clique no link de redefinição e siga as instruções para criar uma nova senha.

Caso você não receba o e-mail ou encontre dificuldades técnicas, entre em contato com o suporte da FAI através do e-mail **suporte@fai.ufscar.br** ou pelo telefone **(16) 3351-9000**.

> Fonte: [Manual do Sistema Area Coordenadores.pdf, pág. 4]

**Fontes (cards da sidebar):**

- Manual do Sistema Área Coordenadores.pdf (pág. 4 · 97%)
- Manual dos Coordenadores.pdf

---

## SIST-02 — Tela Inicial / Notificações

**Pergunta:** Para que serve o ícone de notificações com aquele numerozinho vermelho no topo da tela?

**Páginas de referência (ground-truth):** 5, 42

**Resposta esperada (fatos-chave):** São comunicados/informes enviados pela FAI aos usuários; o número em vermelho é a quantidade de notificações pendentes. Ao clicar no ícone o sistema exibe as últimas notificações (com indicação de lida/não lida) e zera o contador; 'Ver todas' lista as demais. Após a leitura a notificação deixa de ser apresentada.

**Resposta do chatbot** *(latência 70.2s · skills: consultar_base_conhecimento)*:

O manual não fornece informações sobre ícones de interface, como notificações ou indicadores numéricos em telas do sistema.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-03 — Finanças / Balancete do Projeto

**Pergunta:** No balancete do projeto, qual a diferença entre a visão de saldo 'Projeto' e a visão 'Contábil'?

**Páginas de referência (ground-truth):** 8

**Resposta esperada (fatos-chave):** Projeto = Liberado – (Empenho + Gasto); Contábil = (Orçado + Liberado) – (Empenho + Gasto). A explicação aparece ao posicionar o mouse sobre o botão de Visão de Saldo nos filtros.

**Resposta do chatbot** *(latência 71.1s · skills: consultar_base_conhecimento)*:

O manual não fornece informações sobre a diferença entre as visões de saldo "Projeto" e "Contábil" no balancete.

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-04 — Recursos Humanos / Bolsistas (Proposta de Bolsa)

**Pergunta:** Cadastrei a proposta de bolsa, o membro aceitou a proposta e eu aprovei o pagamento, mas o bolsista não recebeu. O que pode estar faltando?

**Páginas de referência (ground-truth):** 12

**Resposta esperada (fatos-chave):** Falta o Aceite do Termo de Outorga de Bolsa: o sistema gera o Termo e envia por e-mail ao membro, que deve finalizar com a assinatura eletrônica. Enquanto não houver esse aceite, nenhum pagamento é realizado, independentemente da aprovação pelo coordenador.

**Resposta do chatbot** *(latência 68.9s · skills: consultar_base_conhecimento)*:

O manual não detalha os motivos específicos para um bolsista não receber o pagamento após a aprovação da proposta e do pagamento.

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-05 — Recursos Humanos / Ações do Coordenador sobre pagamentos de bolsa

**Pergunta:** Qual a diferença entre suspender e cancelar um pagamento de bolsa pendente?

**Páginas de referência (ground-truth):** 13

**Resposta esperada (fatos-chave):** Suspensão é temporária, exige justificativa e permite aprovar o pagamento posteriormente; cancelamento é definitivo, exige justificativa e não permite aprovação posterior. Já a aprovação é automática: ao clicar o pagamento é autorizado (clicou -> pagou), sem ações posteriores.

**Resposta do chatbot** *(latência 91.8s · skills: consultar_base_conhecimento)*:

O manual não fornece informações sobre a diferença entre suspender e cancelar um pagamento de bolsa pendente.

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-06 — Faturamento / Emissão de Pedido de Venda

**Pergunta:** Cadastrei um pedido de venda hoje de manhã. Quando a nota fiscal vai ser emitida?

**Páginas de referência (ground-truth):** 15

**Resposta esperada (fatos-chave):** O faturamento é realizado duas vezes ao dia: pedidos cadastrados pela manhã são faturados à tarde e os cadastrados à tarde, na manhã do dia seguinte. Os dados vão direto ao Sapiens, sem intervenção/conferência da FAI.

**Resposta do chatbot** *(latência 57.4s · skills: consultar_base_conhecimento)*:

O faturamento da nota fiscal ocorre duas vezes ao dia, seguindo o cronograma abaixo:

*   **Pedidos cadastrados pela manhã:** são faturados no período da tarde do mesmo dia;
*   **Pedidos cadastrados à tarde:** são faturados no período da manhã do dia seguinte.

Como você informou que realizou o cadastro hoje de manhã, a nota fiscal deve ser emitida no período da tarde deste mesmo dia.

> Fonte: [Manual do Sistema Area Coordenadores.pdf, pág. 15]

**Fontes (cards da sidebar):**

- Manual do Sistema Área Coordenadores.pdf (pág. 15 · 46%)
- Manual dos Coordenadores.pdf

---

## SIST-07 — Faturamento / Item de Serviço do Pedido de Venda

**Pergunta:** Existe limite de texto na descrição do item de serviço quando emito um pedido de venda?

**Páginas de referência (ground-truth):** 17

**Resposta esperada (fatos-chave):** Sim: máximo de 250 caracteres por item e total de 500 caracteres no Pedido; o limite é imposto pelo software emissor da NFS (Nota Fiscal de Serviço) utilizado pela Prefeitura Municipal.

**Resposta do chatbot** *(latência 33.5s · skills: consultar_base_conhecimento)*:

O manual estabelece os seguintes limites para a descrição do item de serviço em um pedido de venda:

*   **Por item:** Máximo de **250 caracteres**.
*   **Na ordem (total):** Máximo de **500 caracteres**.

> Fonte: [Manual do Sistema Area Coordenadores.pdf, pág. 17]

**Fontes (cards da sidebar):**

- Manual do Sistema Área Coordenadores.pdf (pág. 17 · 92%)
- Manual dos Coordenadores.pdf

---

## SIST-08 — Relatórios / Custo Operacional por Período (COP, Ressarcimento e Retribuição)

**Pergunta:** No relatório de Custo Operacional por Período, o que muda entre as visões Recebimento e Pagamento?

**Páginas de referência (ground-truth):** 19

**Resposta esperada (fatos-chave):** Recebimento (seleção pela data de recebimento dos títulos de faturamento) mostra quanto cada título recebido pagou de despesas por alínea, com taxas (%) e resumo à direita; consulta inicial exibe os últimos 30 dias. Pagamento (seleção pela data de pagamento das despesas) mostra como cada título de pagamento foi composto pelos títulos de recebimento.

**Resposta do chatbot** *(latência 36.7s · skills: consultar_base_conhecimento)*:

No relatório de **Custo Operacional por Período**, as duas visões apresentam perspectivas diferentes sobre a relação entre os títulos de recebimento e pagamento:

*   **Recebimento**: mostra os valores que cada título recebido pagou a título de despesas.
*   **Pagamento**: exibe a composição de cada título de pagamento de despesas com os títulos de recebimento.

O relatório foi desenvolvido para facilitar o gerenciamento do projeto e tornar transparente os valores cobrados, que são frequentemente analisados pelos coordenadores. 

> Fonte: [Manual do Sistema Area Coordenadores.pdf, pág. 19]

**Fontes (cards da sidebar):**

- Manual do Sistema Área Coordenadores.pdf (pág. 19 · 90%)
- Manual dos Coordenadores.pdf

---

## SIST-09 — Formulários Eletrônicos / Acompanhamento (ícones de trâmite)

**Pergunta:** Apareceu um alerta vermelho na coluna do último trâmite de um formulário que eu enviei. O que isso significa?

**Páginas de referência (ground-truth):** 25

**Resposta esperada (fatos-chave):** Alerta vermelho indica que o formulário foi Rejeitado pela Fundação (o amarelo indica que foi alterado). Na rejeição, um e-mail com a justificativa é enviado ao Emissor, ao Coordenador e ao Analista responsável, e os formulários rejeitados ficam em aba específica para consulta.

**Resposta do chatbot** *(latência 37.5s · skills: consultar_base_conhecimento)*:

O alerta vermelho na coluna de **Último Trâmite** indica que o formulário foi **rejeitado pela Fundação**.

Nesses casos, a Fundação envia um e-mail para o emissor, para o coordenador e para o analista responsável, contendo a justificativa da rejeição.

Como informação adicional, um ícone amarelo na mesma coluna indica que o formulário foi alterado pela Fundação.

> Fonte: [Manual do Sistema Area Coordenadores.pdf, pág. 25]

**Fontes (cards da sidebar):**

- Manual do Sistema Área Coordenadores.pdf (pág. 25 · 96%)
- Manual dos Coordenadores.pdf

---

## SIST-10 — Formulários Eletrônicos / Acompanhamento SC (Solicitação de Compra)

**Pergunta:** Depois que envio uma solicitação de compra eletrônica, como acompanho no sistema o andamento da compra até o pagamento do fornecedor?

**Páginas de referência (ground-truth):** 27

**Resposta esperada (fatos-chave):** Pela aba Acompanhamento SC, que mostra a cadeia vinda do Sapiens (ERP): SC eletrônica -> Solicitação(ões) de Compra Sapiens -> Ordem(ns) de Compra -> Nota(s) Fiscal(is) -> Título(s), com data de pagamento (vazia = não pago). Na tela também há o botão Enviar NF (formulário SC-NF) e filtros Todos/Andamento por período.

**Resposta do chatbot** *(latência 45.2s · skills: consultar_base_conhecimento)*:

Para acompanhar o andamento de uma solicitação de compra eletrônica (SC) até o pagamento ao fornecedor no sistema **Área de Coordenadores**, você deve seguir os passos abaixo:

1.  **Acesso à aba "Acompanhamento SC"**: No menu lateral da Área de Coordenadores, acesse a opção *Solicitações* e selecione *Acompanhamento SC*. Nesta tela, é possível visualizar todas as SCs criadas e identificar seus status atuais (como aguardando aprovação, aprovada, ordem gerada, NF recebida, título criado ou pagamento efetuado).
2.  **Visualização de detalhes**: Ao clicar no número da SC específica, você será direcionado para uma página de acompanhamento detalhada que exibe:
    *   **Ordens de Compra (OC)**: links para cada OC gerada pela SC;
    *   **Notas Fiscais Eletrônicas (NF-E)**: links para as notas emitidas pelo fornecedor;
    *   **Títulos**: links para os títulos gerados a partir da NF, indicando se o pagamento já foi realizado ou se ainda está pendente.
3.  **Confirmação no Faturamento**: Caso precise de uma visão direta sobre o status do pagamento, você pode acessar o menu *Faturamento*. Na tela inicial, haverá um bloco específico para **Título a Receber**, que indica se o status é "Pago" ou se ainda está em aberto.

Vale ressaltar que todas as informações são atualizadas automaticamente pelo sistema Sapiens (ERP), não sendo necessária qualquer sincronização manual por parte do usuário.

> Fonte: [Manual do Sistema Area Coordenadores.pdf, págs. 14, 25, 27, 37]

**Fontes (cards da sidebar):**

- Manual do Sistema Área Coordenadores.pdf (pág. 14 · 57%)
- Manual do Sistema Área Coordenadores.pdf (pág. 27 · 83%)
- Manual do Sistema Área Coordenadores.pdf (pág. 37 · 88%)
- Manual dos Coordenadores.pdf

---

## SIST-11 — Formulários / Protocolo Eletrônico e aprovação

**Pergunta:** Acabei de aprovar um formulário. Por que o pessoal da FAI ainda não está conseguindo visualizá-lo?

**Páginas de referência (ground-truth):** 30

**Resposta esperada (fatos-chave):** Somente após a aprovação eletrônica pelo Coordenador/Aprovador o formulário recebe número de Protocolo Eletrônico e passa a ser visível aos colaboradores da FAI; além disso, há uma proteção que retém a entrega do formulário por 10 minutos após a aprovação.

**Resposta do chatbot** *(latência 83.5s · skills: consultar_base_conhecimento, verificando_fontes)*:

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-12 — Formulários Eletrônicos / SP – Solicitação de Pagamento (rascunho e upload)

**Pergunta:** Estava preenchendo uma SP e a aba do navegador fechou antes de eu anexar a nota fiscal. Perdi tudo?

**Páginas de referência (ground-truth):** 33

**Resposta esperada (fatos-chave):** Não: a primeira tela da SP fica salva com status Rascunho e pode ser acessada em Ficha do Projeto / Formulários para retomar o preenchimento e anexar os comprovantes na tela de Upload (documento fiscal obrigatório, boletos e orçamentos se for o caso).

**Resposta do chatbot** *(latência 89.7s · skills: consultar_base_conhecimento, verificando_fontes)*:

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-13 — Formulários Eletrônicos / TR – Transferência de Valores

**Pergunta:** Quais tipos de transferência eu consigo fazer pelo formulário TR e ele chega na hora para o Setor de Projetos?

**Páginas de referência (ground-truth):** 35

**Resposta esperada (fatos-chave):** Tipos: Entre Projetos, Empréstimo (somente FAI • UFSCar) e Devolução de Empréstimo. O formulário só é exibido para o Setor de Projetos 30 minutos após a Aprovação; se o emissor for Coordenador/Aprovador a aprovação é automática, se for Auxiliar/Membro precisa ser aprovado em Formulários/Visualizar.

**Resposta do chatbot** *(latência 144.1s · skills: consultar_base_conhecimento, verificando_fontes, consultar_base_conhecimento)*:

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-14 — Formulários Eletrônicos / SF-PC – Suprimento de Fundos - Prestação de Contas

**Pergunta:** Como faço a prestação de contas de um suprimento de fundos pelo sistema?

**Páginas de referência (ground-truth):** 39

**Resposta esperada (fatos-chave):** Em Formulários, selecionar a aba Adiantamento de Recursos, localizar o formulário pelo filtro (status e período, buscando pela lupa) e clicar em Prestar Contas; distribuir o valor das despesas (Rateio) pelas Contas Financeiras/Alíneas (o sistema atualiza o total, botão '+' para novos itens), Enviar, Imprimir a Prestação de Contas e anexar os comprovantes originais encaminhando à FAI.

**Resposta do chatbot** *(latência 73.2s · skills: consultar_base_conhecimento)*:

O manual não detalha o procedimento específico para a prestação de contas de suprimento de fundos por meio do sistema.

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---

## SIST-15 — Gerenciando os Acessos / Perfis de acesso

**Pergunta:** Quero que minha auxiliar veja todos os formulários do projeto, não só os que ela mesma emitiu. Que perfil de acesso eu dou para ela?

**Páginas de referência (ground-truth):** 40, 41

**Resposta esperada (fatos-chave):** Atribuir o perfil FormuláriosProjeto, que permite visualizar todos os formulários do projeto independentemente do emissor (FormulárioMembro só mostra formulários em que o membro é emissor ou favorecido). A atribuição é feita em Gerenciar Acessos (menu lateral 'Área de Coordenadores' ou aba Acessos em Dados do Projeto): pesquisar por CPF/nome, clicar no ícone Gerenciar Acessos e marcar a funcionalidade na matriz projetos x funcionalidades.

**Resposta do chatbot** *(latência 71.2s · skills: consultar_base_conhecimento)*:

O manual não detalha os perfis de acesso específicos para visualização de formulários por parte de auxiliares ou outros membros da equipe.

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---
