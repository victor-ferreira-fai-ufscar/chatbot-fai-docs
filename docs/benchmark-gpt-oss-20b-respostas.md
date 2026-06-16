# Benchmark `gpt-oss:20b` — respostas completas

Corrida da **mesma bateria de 9 perguntas** pela rota real do chatbot
(`POST /api/v1/chat/stream` → LightRAG modo híbrido → Ollama), capturando a
**resposta completa** de cada pergunta.

- **Data:** 16/06/2026
- **Modelo (LLM):** `gpt-oss:latest` (20,9B, MoE, quant MXFP4 ~13,8 GB) ·
  **Embeddings:** `bge-m3:latest`
- **Hardware:** NVIDIA RTX 5090 (32 GB)
- **Condições:** cada pergunta como conversa nova (sem histórico).
- **Resultado:** **9/9 respostas completas**, sem truncagem. Média TTFT 10,0s ·
  total **15,7s** — mais rápido que `gemma4:12b` (33,6s) apesar de ser um modelo
  de **raciocínio** (pensa antes de responder). O `<think>`/análise fica fora do
  campo `content`. Respostas mais detalhadas e estruturadas (tabelas, listas).

> ⚠️ **Duas ressalvas de precisão factual** a conferir no manual antes de adotar
> em produção:
> - **Q4:** citou limite de "**acima de 10 salários-mínimos**" para exigir 3
>   orçamentos — número não mencionado pelos outros modelos; verificar.
> - **Q7:** respondeu apenas "**Setor de Projetos**"; o `gemma4:12b` deu resposta
>   mais ampla (equipes via Gestor do Projeto + e-mail/telefone/presencial).
>   Conferir qual reflete o manual.

## Tempos

| Q | TTFT | Total | Chars |
|---|---|---|---|
| Q1 | 2,2s | 6,8s | 1346 |
| Q2 | 7,7s | 13,2s | 1223 |
| Q3 | 11,2s | 17,5s | 1241 |
| Q4 | 7,4s | 16,7s | 1133 |
| Q5 | 8,3s | 14,6s | 2203 |
| Q6 | 7,2s | 12,6s | 392 |
| Q7 | 30,4s | 35,2s | 278 |
| Q8 | 8,3s | 13,1s | 1006 |
| Q9 | 7,0s | 11,2s | 365 |

**Médias:** TTFT ~10,0s · total ~15,7s · ~1021 chars. (Q7 foi o único outlier de
tempo — raciocinou bem mais.)

## Respostas

### Q1 — Como a FAI diferencia legalmente uma "obra" de um "serviço de engenharia comum" e de um "serviço especial"?

| Conceito | Definição jurídica (FAI) | Característica distintiva |
|----------|---------------------------|---------------------------|
| **Obra** | "Toda atividade legalmente privativa de arquitetos e engenheiros que inova ou altera substancialmente o espaço físico de um imóvel." | Intervenção física no patrimônio, exigindo planejamento técnico e aprovação conforme leis como a Lei Federal nº 5.194/668. |
| **Serviço de Engenharia Comum** | "Serviço de engenharia que é padronizável e permite descrição objetiva." | Pode ser descrito objetivamente e reutilizado em situações semelhantes; não altera significativamente o espaço físico. |
| **Serviço de Engenharia Especial** | "Serviço de engenharia que, devido à alta heterogeneidade ou complexidade, exige justificativa e estudos técnicos para comprovar a inviabilidade de padronização." | Cada demanda é única e requer documentação técnica detalhada antes de ser aprovada. |

Essas distinções influenciam a modalidade de licitação, os requisitos de documentação e o acompanhamento técnico da execução.

> Fonte: M-coordenadoresFAI-01-06

### Q2 — Além da aprovação da chefia, a autorização da SeGEF é o único trâmite para instalar um posto de transformação e adequações elétricas?

Não — a SeGEF é indispensável, mas não é o único trâmite:

- **SeGEF**: analisa e aprova projetos de obras nos campi (conformidade com o Código de Obras e diretrizes do ZAU).
- **FAI-UFSCar (Coordenador)**: elabora **Termo de Referência** e envia ao setor de Projetos da FAI para a orçamentação pela Fundação, dentro do plano de aplicação.
- **Gerência de Engenharia**: faz acompanhamento e fiscalização; antes de iniciar as atividades elétricas é preciso obter sua avaliação técnica e autorização.

> Fonte: M-coordenadoresFAI-01-06

### Q3 — Intervenção física custeada integralmente com recursos privados: preciso seguir a Lei 14.133/2021 e o Decreto 8.241/2014?

Não — esses instrumentos aplicam-se apenas quando há **recursos públicos**. Para recursos privados valem as normas internas:

- **Processos em andamento**: Resolução Interna **CD/FAI nº 12/21**.
- **Novos processos (a partir de 26/01/2026)**: Resolução Interna **CD/FAI nº 13/26**.

Essas resoluções definem modalidades de compra, formulários e requisitos administrativos. Ainda assim, valem os princípios gerais da administração pública (legalidade, impessoalidade, moralidade, publicidade, eficiência, economicidade).

> Fonte: M-coordenadoresFAI-01-06

### Q4 — Para acelerar a orçamentação de uma modificação no layout, devo submeter 3 orçamentos formais à Gerência de Engenharia?

Não para a entrega inicial. O coordenador apresenta **apenas 1 orçamento** como base de referência técnica e financeira. Os **3 orçamentos formais** só são exigidos depois, na etapa de compra/contratação, quando o valor ultrapassa o limite (citado como "acima de 10 salários-mínimos nacionais") — e isso se aplica ao processo de aquisição, não à entrega do orçamento base à Gerência de Engenharia.

> Fontes: M-coordenadoresFAI-01-06; Knowledge Graph "Compra ou Alienação Processo"
>
> ⚠️ Conferir o limite de "10 salários-mínimos" no manual (não citado por outros modelos).

### Q5 — Como a fiscalização da FAI documenta imprevistos técnicos que afetem custo, qualidade ou prazo?

Cinco mecanismos:

1. **Registros formais dos engenheiros**: documentação técnica atualizada, relatórios de campo descrevendo alterações de carga/infraestrutura/dimensionamento.
2. **Atualização do cronograma físico-financeiro**: reflete novo escopo, custos e prazos; mantido no portal da Área de Coordenadores.
3. **Formalização via Termo Aditivo**: para mudança de objeto, prazo ou valor — com justificativa técnica, aprovado por Engenharia, Finanças e Jurídico.
4. **Registro na plataforma Área de Coordenadores**: relatórios, cronogramas e aditivos carregados com histórico de versões.
5. **Relatório final de conclusão**: seção específica sobre imprevistos e medidas corretivas, para prestação de contas.

> Fonte: M-coordenadoresFAI-01-06

### Q6 — O Coordenador deve prever recursos para contratação de projetos de engenharia e orçamento base no Projeto/Convênio em obras novas e/ou reformas?

Sim. Em obras novas ou reformas, o coordenador deve prever os recursos e incluir um **orçamento base (proforma)** no Projeto/Convênio. Envia **01 (um) orçamento** como base de referência de preço e especificações.

> Fonte: M-coordenadoresFAI-01-06

### Q7 — Em caso de dúvidas e/ou agendamento de reuniões iniciais, qual setor da FAI deve ser contatado?

Respondeu: o **Setor de Projetos** da FAI-UFSCar, que coordena a abertura de processos, análise de demandas e questões de execução de projetos.

> Fonte: M-coordenadoresFAI-01-06
>
> ⚠️ Diverge do `gemma4:12b` (que indicou equipes especializadas via Gestor do Projeto + canais e-mail/telefone/presencial). Conferir no manual.

### Q8 — Posso comprar materiais com meu próprio dinheiro e pedir reembolso total à FAI?

Em regra, **não** é autorizado o ressarcimento de compras/serviços feitos diretamente pelo coordenador. O reembolso só cabe quando: a despesa está prevista no plano de aplicação; é permitida pelo financiador; e há documento fiscal legível em nome da FAI (ou com CNPJ/CPF em branco). Alternativas recomendadas: **Suprimento de Fundos** (adiantamento, quando autorizado) ou as modalidades **Compra Direta / Compra Fácil** via plataforma oficial.

> Fonte: M-coordenadoresFAI-01-06, pág. 70

### Q9 — Cupom fiscal com meu CPF impresso é aceito na prestação de contas?

Não — cupons com CPF/nome de pessoa física não são aceitos. Devem conter o **CNPJ da FAI** ou ter o campo CPF/CNPJ **em branco**. Exceção: comprovantes de envio dos **Correios**.

> Fonte: M-coordenadoresFAI-01-06
