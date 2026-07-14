# Bateria de Testes — Manual do Coordenador (processos FAI)

> **Data:** 2026-07-14 · **Perguntas:** 15 (respondíveis SOMENTE por este manual)
> **Ground-truth:** `docs/manual_coordenadores_page_marked.txt` (marcadores `[PÁGINA N]` = página real do PDF)
> **Config do chat:** modo agêntico ON (gemma4:12b) · LightRAG `mix` (gpt-oss think=high) · mitigações multi-manual ativas (regra 4.5, guard de grounding, validação citação×recuperado)
> **Status:** respostas preenchidas (15/15)

As *páginas de referência* e a *resposta esperada* vêm do ground-truth e servem para conferir manualmente a qualidade de cada resposta (a fonte citada deve apontar para essas páginas do `Manual dos Coordenadores.pdf`).

---

## COORD-01 — Marco legal — legislação sobre aquisições

**Pergunta:** Meu projeto é financiado com recursos públicos. Quais normas regem as compras e contratações de serviços nesse caso?

**Páginas de referência (ground-truth):** 11, 70

**Resposta esperada (fatos-chave):** As compras e contratações com recursos públicos são norteadas primordialmente pelo Decreto nº 8.241/2014 (aquisição de bens e contratação de obras e serviços pelas fundações de apoio), aplicando-se de forma subsidiária os princípios e diretrizes da Lei nº 14.133/2021 (Nova Lei de Licitações e Contratos).

**Resposta do chatbot** *(latência 67.4s · skills: consultar_base_conhecimento)*:

Para compras e contratações de serviços com recursos públicos, o manual estabelece as seguintes normas e procedimentos:

**Base Legal e Princípios**
As aquisições devem seguir os princípios da legalidade, economicidade, impessoalidade, transparência e eficiência. As bases legais citadas para este tema são:
*   Decreto nº 8.241/2014 (regulação de aquisição de bens e contratação de obras e serviços por fundações de apoio);
*   Lei nº 14.133/2021 (Nova Lei de Licitações e Contratos, aplicada subsidiariamente);
*   Portaria nº 448/2002 (critérios de classificação das despesas).

**Modalidades de Contratação**
O manual define três caminhos principais dependendo do valor e da situação:
1.  **Compra Direta:** Permitida para valores inferiores a R$ 100.000,00 (obras ou serviços) ou R$ 40.000,00 (outros serviços e compras). Exige justificativa técnica e pesquisa de preços.
2.  **Seleção Pública:** Utilizada quando o valor ultrapassa os limites da compra direta; trata-se de um processo licitatório com critérios objetivos.
3.  **Contratação por Inexigibilidade:** Aplicável quando há apenas um fornecedor ou a competição é inviável, exigindo justificativa detalhada e parecer jurídico.

**Procedimento Geral**
O fluxo para a realização das contratações envolve:
*   Identificação da necessidade e elaboração do plano de aplicação/trabalho (aprovado pela FAI e pela instituição parceira).
*   Realização de pesquisa de mercado e obtenção de orçamentos (exceto para itens "Compra Fácil").
*   Elaboração de Termo de Referência, quando necessário.
*   Submissão do pedido via sistema **Área de Coordenadores** da FAI•UFSCar, com posterior aprovação do coordenador e assinatura do contrato pela Fundação.

**Documentação Exigida**
Para cada aquisição, é necessária a apresentação de nota fiscal, recibo ou fatura em nome da FAI•UFSCar. Para compras complexas, deve-se incluir o Termo de Referência e demais documentos técnicos pertinentes ao plano de aplicação aprovado.

Todas as solicitações (compras, importações, financeiro, pessoal e viagens) devem ser realizadas pelo sistema **Área de Coordenadores**, onde é possível acompanhar status e pendências em tempo real.

> Fonte: [Manual dos Coordenadores.pdf, págs. 11, 19, 30, 32, 33]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 11 · 96%)
- Manual dos Coordenadores.pdf (pág. 19 · 6%)
- Manual dos Coordenadores.pdf (pág. 30 · 71%)
- Manual dos Coordenadores.pdf (pág. 32 · 71%)
- Manual dos Coordenadores.pdf (pág. 33 · 71%)

---

## COORD-02 — Agentes do projeto e responsabilidades

**Pergunta:** Qual é exatamente o papel do fiscal do projeto? O que ele faz?

**Páginas de referência (ground-truth):** 15

**Resposta esperada (fatos-chave):** O fiscal acompanha e fiscaliza a execução do projeto, verifica a correta aplicação dos recursos, emite relatórios de conformidade e recomenda ajustes, atesta o cumprimento/recebimento de cada etapa ou entrega e analisa e aprova a Prestação de Contas Final do projeto.

**Resposta do chatbot** *(latência 35.9s · skills: consultar_base_conhecimento)*:

O Fiscal do Projeto tem a função de acompanhar e fiscalizar a execução do projeto, garantindo que os recursos sejam aplicados corretamente. Suas principais responsabilidades incluem:

*   **Acompanhamento e fiscalização**: monitorar a execução das atividades previstas no cronograma;
*   **Verificação de recursos**: assegurar a correta aplicação dos recursos financeiros e materiais;
*   **Relatórios de conformidade**: emitir relatórios contendo recomendações quando necessário;
*   **Atestes**: atestar o cumprimento ou recebimento de cada etapa ou entrega do projeto;
*   **Prestação de Contas**: analisar e aprovar a Prestação de Contas Final do projeto.

> Fonte: [Manual dos Coordenadores.pdf, pág. 15]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 15 · 73%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-03 — Formalização de projetos e convênios

**Pergunta:** Meu convênio envolve repasse de recursos federais. Sou obrigado a usar alguma plataforma do governo para a gestão dele?

**Páginas de referência (ground-truth):** 21

**Resposta esperada (fatos-chave):** Sim: a Plataforma TransfereGov (mantida pelo Ministério da Gestão e da Inovação em Serviços Públicos) é o instrumento de gestão obrigatório para convênios e termos de parceria que envolvem transferência de recursos da União, garantindo transparência, padronização e controle do início ao fim da parceria.

**Resposta do chatbot** *(latência 59.4s · skills: consultar_base_conhecimento)*:

Sim, o uso da plataforma **TransfereGov** é obrigatório para convênios (e termos de parceria) que envolvam a transferência de recursos da União para a execução de projetos.

Essa plataforma, mantida pelo Ministério da Gestão e da Inovação em Serviços Públicos, permite registrar, acompanhar e controlar as transferências de recursos federais, garantindo transparência, padronização e controle do início ao fim da parceria. Os coordenadores de projeto utilizam o TransfereGov para submeter pedidos, monitorar status e garantir a correta aplicação dos recursos.

> Fonte: [Manual dos Coordenadores.pdf, pág. 21]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 21 · 62%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-04 — Gestão financeira — documentos de pagamento

**Pergunta:** Até quando preciso enviar as notas fiscais do projeto para a FAI? O que acontece se eu atrasar?

**Páginas de referência (ground-truth):** 25, 71

**Resposta esperada (fatos-chave):** As notas fiscais devem ser enviadas à FAI dentro do mês de sua emissão ou até o 5º dia do mês subsequente, sempre identificando o projeto. O não envio no prazo pode acarretar multa e implicações legais ao projeto ou à Fundação.

**Resposta do chatbot** *(latência 49.5s · skills: consultar_base_conhecimento)*:

Para o envio das notas fiscais ao FAI•UFSCar, as orientações são as seguintes:

*   **Prazo de envio:** As notas devem ser enviadas à Fundação dentro do mês em que foram emitidas ou, no máximo, até o **5º dia útil do mês subsequente**.
*   **Consequências do atraso:** O não cumprimento deste prazo pode acarretar multas e implicações legais tanto para o projeto quanto para a Fundação.

> Fonte: [Manual dos Coordenadores.pdf, pág. 25]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 25 · 61%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-05 — Execução de despesas — ressarcimento de pequenas despesas

**Pergunta:** Paguei do meu bolso uma despesa pequena e urgente do projeto. Existe limite de valor para pedir ressarcimento à FAI?

**Páginas de referência (ground-truth):** 27

**Resposta esperada (fatos-chave):** Despesas eventuais de pequeno vulto podem ser ressarcidas até o limite de três vezes o maior salário-mínimo nacional vigente por projeto, mediante solicitação justificada do coordenador e aprovação da Gerência de Projetos. É proibido usar esses recursos para contratação de pessoas físicas, prestação de serviços e aquisição de material permanente.

**Resposta do chatbot** *(latência 37.1s · skills: consultar_base_conhecimento)*:

Para despesas urgentes ou pequenas pagas pelo coordenador ou pesquisador, o reembolso está limitado a **três vezes o maior salário-mínimo nacional vigente por projeto**, desde que permitido e compatível com as regras do financiador e aprovado pela Gerência de Projetos.

> Fonte: [Manual dos Coordenadores.pdf, pág. 27]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 27 · 33%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-06 — Modalidades de aquisição — compra direta (recursos públicos)

**Pergunta:** Até que valor a FAI consegue fazer compra direta com recursos públicos, sem precisar de seleção pública?

**Páginas de referência (ground-truth):** 32, 65

**Resposta esperada (fatos-chave):** Pelo Decreto nº 8.241/2014, a compra direta é admitida para obras e serviços de engenharia em valor inferior a R$ 100.000,00 e para outros serviços e compras em valor inferior a R$ 40.000,00 (desde que não sejam parcelas de um mesmo objeto de maior vulto). Acima desses limites, realiza-se Seleção Pública.

**Resposta do chatbot** *(latência 35.5s · skills: consultar_base_conhecimento)*:

Para a realização de compras diretas com recursos públicos sem a necessidade de seleção pública (dispensa de licitação), os limites estabelecidos pelo manual são:

*   **Obras e serviços de engenharia:** até **R$ 100.000,00**.
*   **Outros serviços e compras:** até **R$ 40.000,00**.

> Fonte: [Manual dos Coordenadores.pdf, pág. 32]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 32 · 52%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-07 — Modalidades de aquisição — compras com recursos privados

**Pergunta:** No meu projeto com recursos privados, a partir de que valor a compra deixa de ser direta e passa a exigir mais orçamentos?

**Páginas de referência (ground-truth):** 32

**Resposta esperada (fatos-chave):** Pela Resolução FAI.UFSCar nº 013/2026 (Art. 31), a compra direta com simples pesquisa de mercado vale para aquisições de até 10 vezes o maior salário-mínimo nacional; acima disso, a compra é feita por processo, com pesquisa de mercado e coleta de no mínimo 3 orçamentos formais.

**Resposta do chatbot** *(latência 68.6s · skills: consultar_base_conhecimento)*:

Para projetos com recursos privados, o manual estabelece as seguintes diretrizes sobre a modalidade de **Compra Direta**:

*   **Limites de valor para Compra Direta:**
    *   **Obras e serviços de engenharia:** até R$ 100.000,00.
    *   **Outros serviços e compras:** até R$ 40.000,00.

Em relação à necessidade de múltiplos orçamentos para projetos com recursos privados, o manual não estabelece essa exigência. É necessário anexar apenas um orçamento ou cotação preliminar ao formulário de solicitação de compra (exceto para itens da "Compra Fácil"), seguindo os procedimentos de pesquisa de mercado e obtenção de orçamentos.

> Fonte: [Manual dos Coordenadores.pdf, págs. 31, 32]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 31 · 72%)
- Manual dos Coordenadores.pdf (pág. 32 · 72%)

---

## COORD-08 — Aquisição de produtos controlados

**Pergunta:** Preciso comprar um produto controlado que ainda não está nas licenças da FAI. Quanto tempo leva para incluir e quais restrições existem?

**Páginas de referência (ground-truth):** 30, 33

**Resposta esperada (fatos-chave):** A inclusão de novos itens nas licenças da FAI leva cerca de 90 dias (contatar o Setor de Compras: compras.fai@fai.ufscar.br). A quantidade adquirida não pode ultrapassar o limite das licenças, a instituição apoiada também precisa de autorizações válidas, e é vedada a compra de produtos controlados pela modalidade Compra Direta.

**Resposta do chatbot** *(latência 42.9s · skills: consultar_base_conhecimento)*:

Para incluir um produto controlado que não consta nas licenças da FAI, o procedimento e as condições são os seguintes:

*   **Solicitação de Compras (SC):** O item deve ser indicado na Solicitação de Compras; caso ele não esteja listado, a solicitação poderá ser rejeitada ou exigirá a inclusão prévia.
*   **Autorização:** É necessário que o produto esteja autorizado tanto nas licenças da FAI quanto na instituição apoiada que receberá o material.
*   **Contato com o Setor de Compras:** Você deve entrar em contato com o setor responsável pelo e-mail **compras.fai@fai.ufscar.br**, fornecendo os dados técnicos do item e a justificativa para a inclusão.
*   **Prazo:** O trâmite para a inclusão desse tipo de produto leva aproximadamente **90 dias**.

> Fonte: [Manual dos Coordenadores.pdf, pág. 30]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 30 · 94%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-09 — Obras e serviços de engenharia — prazos

**Pergunta:** Estou planejando uma obra no meu projeto. Quanto tempo costuma levar o processo todo, da documentação até o início da obra?

**Páginas de referência (ground-truth):** 36

**Resposta esperada (fatos-chave):** O prazo mínimo para documentação simples (croqui/planta baixa) é de 60 dias, e o tempo médio total do processo (documentação, licitação e início da obra) pode chegar a 20 meses (599 dias). Obras com prazo superior a 300 dias podem sofrer repactuação de valores/reequilíbrio de contrato; o coordenador envia apenas 1 orçamento de referência.

**Resposta do chatbot** *(latência 46.5s · skills: consultar_base_conhecimento)*:

O processo para a realização de obras em projetos de pesquisa envolve diversas etapas de planejamento, documentação e aprovação técnica. De acordo com o manual, os prazos e procedimentos são estruturados da seguinte forma:

### Etapas do Processo
1.  **Planejamento e Documentação:** O coordenador deve elaborar um plano de trabalho detalhado, orçamento (com alíneas), Termo de Referência (quando exigido) e documentos técnicos específicos (como croquis ou plantas baixas). É necessário enviar apenas um orçamento para servir como base de referência de preço.
2.  **Abertura de Processo:** O coordenador abre o processo no sistema SEI e encaminha à Secretaria de Gestão do Espaço Físico (SeGEF) da UFSCar, após anuência da chefia.
3.  **Análise Técnica (SeGEF):** A SeGEF verifica a conformidade com o Código de Obras e Edificações da UFSCar e as diretrizes do Zoneamento Ambiental Urbano (ZAU). Caso necessário, solicita autorizações para intervenções específicas (como uso de contêineres, demolição de paredes ou novas instalações).
4.  **Orçamentação:** A responsabilidade pelo processo de orçamentação é da Fundação.
5.  **Licitação:** Se o valor da obra ultrapassar os limites de compra direta, o processo seguirá as normas de licitação vigentes.
6.  **Início da Obra:** O início ocorre somente após a aprovação das autorizações prévias, conclusão da licitação (se aplicável) e liberação dos recursos.

### Prazos Estimados
O tempo necessário para concluir o ciclo completo depende da complexidade da obra:
*   **Documentação simples (croqui/planta baixa):** 60 dias.
*   **Tempo médio total do processo:** Pode levar até **20 meses** (599 dias) para percorrer todas as etapas, desde a documentação até o início da obra.

> Fonte: [Manual dos Coordenadores.pdf, págs. 35, 36]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 35 · 76%)
- Manual dos Coordenadores.pdf (pág. 36 · 76%)

---

## COORD-10 — Importação de bens e serviços

**Pergunta:** Depois que a proposta de importação é aprovada e a remessa liberada para embarque, quanto tempo demora até a entrega?

**Páginas de referência (ground-truth):** 38

**Resposta esperada (fatos-chave):** Após a aprovação da proposta e a liberação da remessa para embarque, estima-se prazo de aproximadamente 20 dias para as etapas de tramitação logística, procedimentos aduaneiros, entrega e liquidação do processo; recomenda-se cautela em aquisições próximas ao fim da vigência do projeto.

**Resposta do chatbot** *(latência 38.9s · skills: consultar_base_conhecimento)*:

Após a aprovação da proposta e a liberação para embarque, o prazo estimado de entrega é de aproximadamente **20 dias**. Esse período abrange todas as etapas logísticas, procedimentos aduaneiros, entrega e liquidação do processo.

> Fonte: [Manual dos Coordenadores.pdf, pág. 38]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 38 · 98%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-11 — Gestão de viagens e diárias — adiantamento

**Pergunta:** Quem pode receber adiantamento para viagens do projeto e que tipo de despesa esse adiantamento cobre?

**Páginas de referência (ground-truth):** 41

**Resposta esperada (fatos-chave):** O adiantamento cobre exclusivamente despesas com hospedagem, alimentação e transportes em viagens a serviço, e é exclusivo para pessoas formalmente vinculadas ao projeto (CLT, docentes das apoiadas, estagiários, bolsistas, servidores técnico-administrativos e membros externos nomeados na equipe). A prestação de contas posterior é obrigatória; sem ela, novas solicitações ficam impedidas e o valor pode ter de ser devolvido.

**Resposta do chatbot** *(latência 38.9s · skills: consultar_base_conhecimento)*:

Para receber adiantamento para viagens de projeto, as pessoas devem estar formalmente vinculadas ao projeto e nomeadas na equipe de trabalho. Isso inclui:

*   Funcionários contratados sob regime CLT;
*   Docentes das Instituições Apoiadas;
*   Estagiários;
*   Bolsistas;
*   Servidores técnico-administrativos;
*   Membros externos à Instituição Apoiada.

O adiantamento cobre as seguintes despesas:

*   Hospedagem;
*   Alimentação (refeições e lanches);
*   Transportes relacionados a viagens a serviço do projeto.

> Fonte: [Manual dos Coordenadores.pdf, págs. 41, 42]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 41 · 94%)
- Manual dos Coordenadores.pdf (pág. 42 · 94%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-12 — Gestão de pessoas — concessão de bolsas (prazos)

**Pergunta:** Cadastrei um bolsista novo no projeto. Em quanto tempo o cadastro da bolsa é efetivado e em quanto tempo sai o pagamento?

**Páginas de referência (ground-truth):** 47

**Resposta esperada (fatos-chave):** O cadastro da bolsa é efetivado em até 7 dias úteis a contar do recebimento do formulário eletrônico pelo setor de bolsas da Gestão de Pessoas, e o pagamento é realizado em até 3 dias úteis após a aprovação do coordenador.

**Resposta do chatbot** *(latência 42.3s · skills: consultar_base_conhecimento)*:

Para o cadastro e pagamento de bolsas no âmbito da FAI•UFSCar, os prazos estabelecidos são:

*   **Cadastro do bolsista**: O processo deve ser concluído em até **07 (sete) dias úteis**, contados a partir do recebimento do formulário eletrônico pelo setor de bolsas do Departamento de Gestão de Pessoas.
*   **Pagamento da bolsa**: Ocorre em até **03 (três) dias úteis** após a aprovação do coordenador realizada na Área de Coordenadores.

> Fonte: [Manual dos Coordenadores.pdf, pág. 47]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 47 · 94%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-13 — Gestão de pessoas — contratação de estagiários

**Pergunta:** Quantas horas por semana um estagiário pode trabalhar no projeto e qual a duração máxima do estágio?

**Páginas de referência (ground-truth):** 48

**Resposta esperada (fatos-chave):** A jornada é de no máximo 6 horas diárias e 30 horas semanais para estágio não obrigatório; para estágio obrigatório pode chegar a 40 horas semanais, mediante comprovação (previsão no projeto pedagógico e aprovação da instituição de ensino). A duração máxima do estágio é de 2 anos, exceto para pessoas com deficiência (PCDs).

**Resposta do chatbot** *(latência 58.9s · skills: consultar_base_conhecimento)*:

Para um estagiário em projeto, as condições são as seguintes:

*   **Carga horária semanal:** Pode chegar a **até 40 horas por semana**, desde que seja um estágio obrigatório e esteja comprovado pela matriz curricular do curso, com aprovação da instituição de ensino e pelo Termo de Compromisso de Estágio (TCE).
*   **Duração máxima:** O período máximo do estágio é de **2 anos**, exceto para pessoas com deficiência (PCDs).

> Fonte: [Manual dos Coordenadores.pdf, pág. 48]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 48 · 96%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-14 — Segurança e medicina do trabalho

**Pergunta:** Um funcionário do projeto sofreu um acidente de trabalho. O que devo fazer e em qual prazo?

**Páginas de referência (ground-truth):** 58

**Resposta esperada (fatos-chave):** Qualquer acidente de trabalho ou situação de risco deve ser comunicado à área de Gestão de Pessoas em até 24 horas, que adotará as providências cabíveis, incluindo o registro da Comunicação de Acidente de Trabalho (CAT) quando necessário.

**Resposta do chatbot** *(latência 48.8s · skills: consultar_base_conhecimento)*:

Em caso de acidente de trabalho ou situação de risco envolvendo um funcionário do projeto, você deve seguir o seguinte procedimento:

*   **Comunicação imediata:** O fato deve ser comunicado imediatamente ao Departamento de Gestão de Pessoas.
*   **Prazo:** A comunicação deve ocorrer em até **24 horas** após a ocorrência.

Após receber a notificação, o departamento responsável adotará as providências cabíveis e realizará o registro da Comunicação de Acidente de Trabalho (CAT), quando necessário.

> Fonte: [Manual dos Coordenadores.pdf, pág. 58]

**Fontes (cards da sidebar):**

- Manual dos Coordenadores.pdf (pág. 58 · 63%)
- Manual do Sistema Área Coordenadores.pdf

---

## COORD-15 — Acompanhamento de projetos — remanejamento de saldos entre rubricas

**Pergunta:** Sobrou saldo em uma rubrica do orçamento e falta em outra. Posso remanejar esses recursos? Quais são as condições?

**Páginas de referência (ground-truth):** 59

**Resposta esperada (fatos-chave):** O remanejamento entre rubricas orçamentárias é permitido em alguns casos, desde que previsto no edital, restrito ao limite de 20% da rubrica, autorizado pelo órgão financiador e formalizado junto à FAI UFSCar.

**Resposta do chatbot** *(latência 80.3s · skills: consultar_base_conhecimento)*:

Para esclarecer essa demanda específica, recomendo entrar em contato com o Gestor do seu Projeto. Caso ainda não tenha um gestor designado, procure o Supervisor de Projetos Específicos ou o Supervisor de Projetos Gerais pelo telefone (16) 3351-9000 ou e-mail fai@fai.ufscar.br.

**Fontes (cards da sidebar):**

_(nenhum card)_

---
