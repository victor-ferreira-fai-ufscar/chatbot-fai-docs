# Benchmark `gemma4:12b` — respostas completas

Corrida da **mesma bateria de 9 perguntas** pela rota real do chatbot
(`POST /api/v1/chat/stream` → LightRAG modo híbrido → Ollama), capturando a
**resposta completa** de cada pergunta.

- **Data:** 16/06/2026
- **Modelo (LLM):** `gemma4:12b` · **Embeddings:** `bge-m3:latest`
- **Hardware:** NVIDIA RTX 5090 (32 GB)
- **Condições:** cada pergunta como conversa nova (sem histórico).
- **Resultado:** **9/9 respostas** (na corrida de 15/06 o `gemma4:12b` dera 8/9 —
  Q4 vazia; aqui respondeu todas). Todas citaram o manual
  `M-coordenadoresFAI-01-06`.

## Tempos

| Q | TTFT | Total | Chars | Fontes (págs.) |
|---|---|---|---|---|
| Q1 | 20,0s | 27,0s | 1172 | 34 |
| Q2 | 31,2s | 38,4s | 1226 | — |
| Q3 | 26,2s | 33,0s | 1029 | 10 |
| Q4 | 33,7s | 40,0s | 880 | 36 |
| Q5 | 25,6s | 31,4s | 1161 | 36, 58 |
| Q6 | 32,2s | 40,4s | 1325 | 36, 66 |
| Q7 | 23,4s | 29,6s | 819 | 60 |
| Q8 | 20,4s | 27,5s | 1256 | 70, 71 |
| Q9 | 27,9s | 34,8s | 698 | 24, 70 |

**Médias:** TTFT ~26,7s · total ~33,6s (consistente com os ~32,5s do registro
anterior — `gemma4:12b` segue lento, mas estável nesta corrida).

> ⚠️ Avaliação **qualitativa** (precisão/completude) ainda manual — os tempos
> medem velocidade/custo, não qualidade.

## Respostas

### Q1 — Como a FAI diferencia legalmente uma "obra" de um "serviço de engenharia comum" e de um "serviço especial"?

A FAI define e diferencia as modalidades de obras e serviços de engenharia com base em critérios técnicos, complexidade e impacto no espaço físico. As definições detalhadas são:

- **Obra**: qualquer atividade legalmente privativa de arquitetos e engenheiros que resulte em inovação ou alteração substancial do espaço físico de um imóvel.
- **Serviço de Engenharia**: atividades técnicas profissionais privativas de arquitetos, engenheiros ou técnicos especializados que não se enquadram como "obra" (projetos, supervisão, instalações, reparações, perícias e consultorias).
- **Serviço de Engenharia Comum**: serviço de engenharia que possui caráter padronizável e permite uma descrição objetiva.
- **Serviço de Engenharia Especial**: serviço de engenharia que, devido à sua alta heterogeneidade ou complexidade, exige a apresentação de justificativa e estudos técnicos para comprovar a inviabilidade de padronização.

> Fonte: M-coordenadoresFAI-01-06, pág. 34

### Q2 — Além da aprovação da chefia, a autorização da SeGEF é o único trâmite para instalar um posto de transformação e adequações elétricas?

Para essas demandas, classificadas como **Obras e Serviços de Engenharia**, a autorização da SeGEF **não** é o único trâmite. Por serem demandas de natureza complexa, exigem fluxo de comunicação específico com a FAI•UFSCar. Além da análise da SeGEF (conformidade com o Código de Obras e diretrizes do ZAU):

- **Gerência de Engenharia**: fornece orientações específicas e os documentos essenciais para a execução.
- **Orçamentação**: de responsabilidade direta da FAI•UFSCar.
- **Planejamento prévio**: documentação clara e técnica para garantir qualidade e segurança.

> Fonte: M-coordenadoresFAI-01-06

### Q3 — Intervenção física custeada integralmente com recursos privados: preciso seguir a Lei 14.133/2021 e o Decreto 8.241/2014?

Como o projeto é custeado com **Recursos Privados**, essas normas **não** se aplicam — elas regem primordialmente projetos com **Recursos Públicos**. Para recursos privados a FAI segue regulamentações próprias:

- **Processos em andamento:** Resolução Interna **CD/FAI nº 12/21**.
- **Novos processos (a partir de 26/01/2026):** Resolução Interna **CD/FAI nº 13/26**.

> Fonte: M-coordenadoresFAI-01-06, pág. 10

### Q4 — Para acelerar a orçamentação de uma modificação no layout, devo submeter 3 orçamentos formais à Gerência de Engenharia?

Não. A orçamentação é responsabilidade da FAI•UFSCar; o Coordenador deve enviar **apenas 01 (um) orçamento**, como base de referência de preço e especificações. Para obras/serviços de engenharia, ao identificar a necessidade o Coordenador deve contatar o **Gestor de Projetos** da FAI, que atua como interlocutor oficial junto à **Gerência de Engenharia** (responsável pelas orientações técnicas e documentos de execução).

> Fonte: M-coordenadoresFAI-01-06, pág. 36

### Q5 — Como a fiscalização da FAI documenta imprevistos técnicos que afetem custo, qualidade ou prazo?

A **Gerência de Engenharia** monitora a execução contratual. A documentação ocorre por:

- **Procedimentos formais**: acompanhamento com **cronograma físico-financeiro** cumprido e atualizado.
- **Registro de ocorrências**: situações que impactem **prazo, custo ou qualidade** são registradas detalhadamente (registro técnico).
- **Formalização de alterações (aditivos)**: mudanças de valor, objeto ou prazo são solicitadas antecipadamente, com justificativa, via **termo aditivo**.

> Fontes: M-coordenadoresFAI-01-06, págs. 36 e 58

### Q6 — O Coordenador deve prever recursos para contratação de projetos de engenharia e orçamento base no Projeto/Convênio em obras novas e/ou reformas?

Sim. Requisitos de planejamento:

- **Planejamento financeiro**: todas as despesas previstas no **Plano de Aplicação/Trabalho** (objetivos, atividades, cronograma e rubricas orçamentárias).
- **Dimensionamento e orçamento base**: uso do **Projeto Básico**, que dimensiona a obra/serviço (viabilidade técnica e ambiental, custo e prazo).
- **Referência para orçamentação**: embora a orçamentação seja da FAI, o Coordenador envia **01 (um) orçamento** como base de referência de preço e especificações.

> Fontes: M-coordenadoresFAI-01-06, págs. 36 e 66

### Q7 — Em caso de dúvidas e/ou agendamento de reuniões iniciais, qual setor da FAI deve ser contatado?

As equipes especializadas da FAI•UFSCar — **compras, financeiro, recursos humanos, jurídico, tecnologia da informação e engenharia** — contatadas por intermédio do **Gestor do Projeto**. Canais de suporte:

- **E-mail:** fai@fai.ufscar.br
- **Telefone:** (16) 3351-9000
- **Atendimento presencial:** mediante agendamento prévio.

A **Área de Coordenadores** no portal também serve para gerenciamento de projetos e comunicação com a equipe.

> Fonte: M-coordenadoresFAI-01-06, pág. 60

### Q8 — Posso comprar materiais com meu próprio dinheiro e pedir reembolso total à FAI?

Regra geral: **não** é autorizado o reembolso de compras/serviços. Exceção para despesas de **pequeno valor e urgentes** (pagamento próprio com posterior ressarcimento), desde que:

- permitidas pelo financiador e pela natureza dos recursos;
- valor não ultrapasse **3× o maior salário-mínimo nacional vigente por projeto**;
- **vedado** para contratação de pessoas físicas, prestação de serviços ou material permanente.

Fora desses casos, seguir os processos padrão (Compra Direta ou "Compra Fácil").

> Fontes: M-coordenadoresFAI-01-06, págs. 70 e 71

### Q9 — Cupom fiscal com meu CPF impresso é aceito na prestação de contas?

Não — cupons com **CPF** ou nome de pessoa física não são aceitos. Critérios:

- **Identificação fiscal**: cupom deve conter o **CNPJ da FAI** ou o campo CPF/CNPJ **em branco**.
- **Exceção**: comprovantes de envio dos **Correios**, aceitos mesmo com dados de pessoa física, devido às exigências de autenticação via Gov.br.

> Fontes: M-coordenadoresFAI-01-06, págs. 24 e 70
