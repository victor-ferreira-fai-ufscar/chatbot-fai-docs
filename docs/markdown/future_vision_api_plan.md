# 👁️ Planos Futuros: Integração da Google Cloud Vision API (Híbrido)

Este documento guarda as diretrizes arquiteturais para o futuro da extração de documentos no projeto.
A extração de texto atual dos manuais é rápida graças biblioteca nativa (`pypdf`), mas ela processa estritamente textos digitais puros, cega para formatações mais complexas.

Com a integração planejada da **Google Cloud Vision API**, o RAG do projeto obterá visão autêntica em diversos cenários institucionais práticos.

---

## 1. O Fim dos "PDFs Fantasmas" (Scanners Antigos)
Se um manual institucional for impresso, assinado à caneta e escaneado, hoje ele é invisível para a engine.
**Solução Planejada:** O projeto utilizará o modo `DOCUMENT_TEXT_DETECTION` (OCR avançado) para digitalizar o conteúdo bloqueado nesses PDFs em imagens e injetar no vetor primário.

## 2. Leitura de Prints de Telas e Sistemas 💻
Para dúvidas como: *"Onde clico para lançar minha nota no sistema acadêmico?"* ou *"Qual a estrutura de pastas do RH?"*.
Muitos "Como Fazer" dependem de Prints com botões, caixas e setas. A Vision API lê o conteúdo de cada frame fotográfico, indexando no RAG para permitir busca profunda em ilustrações dentro dos manuais.

## 3. Estratégia Principal a ser Aplicada: O Funil Híbrido 💰
Por tratar-se de uma API paga pela quantidade de imagens e uso, não passaremos massivamente e às cegas todos os PDFs na plataforma do Google Cloud, pois causará impacto financeiro indesejado a cada reindexação.

**A Arquitetura:**
Deve-se adaptar o serviço de separação de documentos em `pdfs.py` criando um Fallback Automático:
1. O pipeline sempre vai tentar puxar a página normalmente com uso de CPU free via texto puro (`pypdf`).
2. Se a avaliação em tempo de execução desta etapa trouxer `Nulo`, vazio, retalhos curtos demais ou strings ininteligíveis, isso assinala um "alerta visual" para referida página.
3. Somente sob essa condição específica dispararemos a Cloud Vision API extraindo com precisão via rede apenas este estilhaço complicado e injetando seu super-resultado (OCR robusto) junto com os outros pedaços no banco do Vector Store. 

*Arquivado para futuras refatorações tecnológicas da busca em RAG Institucional.*
