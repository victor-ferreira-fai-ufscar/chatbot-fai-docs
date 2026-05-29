# Conteúdo do arquivo Markdown baseado nos endpoints extraídos do LightRAG

markdown_content = """# Documentação Técnica: API LightRAG (Módulo de Documentos)

Esta documentação detalha os endpoints disponíveis no LightRAG para a gestão de documentos, processamento de texto e controlo do pipeline de RAG (Retrieval-Augmented Generation).

## 1. Ingestão e Upload de Dados

Estes endpoints permitem a entrada de informação no sistema para posterior indexação e criação do Grafo de Conhecimento.

| Método | Endpoint            | Descrição                                                                                         |
| :----- | :------------------ | :------------------------------------------------------------------------------------------------ |
| `POST` | `/documents/scan`   | Varre o diretório de entrada configurado em busca de novos ficheiros para indexação automática.   |
| `POST` | `/documents/upload` | Permite o upload direto de um ficheiro para o sistema. Retorna um `track_id` para acompanhamento. |
| `POST` | `/documents/text`   | Insere um bloco de texto simples diretamente no motor de busca do RAG.                            |
| `POST` | `/documents/texts`  | Permite a inserção em massa (batch) de múltiplos blocos de texto numa única requisição.           |

## 2. Monitorização e Status do Pipeline

Como o LightRAG processa extrações complexas de entidades e relações, estes endpoints servem para monitorizar o progresso dessas tarefas assíncronas.

| Método | Endpoint                             | Descrição                                                                                        |
| :----- | :----------------------------------- | :----------------------------------------------------------------------------------------------- |
| `GET`  | `/documents/pipeline_status`         | Fornece métricas globais sobre o estado atual de todas as tarefas no pipeline.                   |
| `GET`  | `/documents/track_status/{track_id}` | Consulta o estado específico de um documento ou texto através do seu ID de rastreio.             |
| `POST` | `/documents/reprocess_failed`        | Reinicia o processamento de documentos que falharam durante a extração ou criação de embeddings. |
| `POST` | `/documents/cancel_pipeline`         | Interrompe imediatamente todas as tarefas de processamento em curso.                             |

## 3. Gestão e Listagem de Documentos

Endpoints para visualização e contagem do acervo documental indexado.

| Método | Endpoint                   | Descrição                                                                            |
| :----- | :------------------------- | :----------------------------------------------------------------------------------- |
| `GET`  | `/documents`               | Lista todos os documentos registados no sistema.                                     |
| `POST` | `/documents/paginated`     | Recupera a lista de documentos com suporte a paginação (ideal para dashboards).      |
| `GET`  | `/documents/status_counts` | Retorna o total de documentos agrupados por estado (Ex: processed, failed, pending). |

## 4. Limpeza e Manutenção (Operações Destrutivas)

Endpoints para gerir o ciclo de vida dos dados e limpar caches de processamento.

| Método   | Endpoint                     | Descrição                                                                           |
| :------- | :--------------------------- | :---------------------------------------------------------------------------------- |
| `DELETE` | `/documents`                 | Remove todos os documentos e limpa os registos globais.                             |
| `DELETE` | `/documents/delete_document` | Elimina um documento específico e remove todos os seus chunks e vetores associados. |
| `DELETE` | `/documents/delete_entity`   | Remove uma entidade específica do Grafo de Conhecimento.                            |
| `DELETE` | `/documents/delete_relation` | Remove uma relação específica entre entidades no Grafo.                             |
| `POST`   | `/documents/clear_cache`     | Limpa a cache de respostas do LLM, forçando novas gerações em consultas futuras.    |

---

### Notas de Implementação

- **Persistência:** As operações de deleção afetam as quatro camadas de armazenamento do LightRAG: `KV_STORAGE`, `VECTOR_STORAGE`, `GRAPH_STORAGE` e `DOC_STATUS_STORAGE`.
- **Async Workflow:** Recomenda-se o uso de *polling* no endpoint `/track_status` para interfaces de utilizador que necessitem de feedback em tempo real sobre o upload.
"""

file_path = "lightrag_api_docs.md"

with open(file_path, "w", encoding="utf-8") as f:
    f.write(markdown_content)

print(f"Arquivo gerado em: {file_path}")
