# Caddy deste stack — DESATIVADO (proxy centralizado)

O reverse proxy HTTPS **não roda mais a partir deste repositório**. Ele foi
**centralizado** em **`/srv/docker/caddy`**, que agora roteia este chatbot **e**
os demais serviços da máquina por subdomínio (`lina`/`chat`/`git`.fai.ufscar.br)
além do acesso histórico por IP (`https://200.136.209.229`). A CA interna desta
pasta (`./caddy/data`) foi migrada para lá, então a confiança foi preservada.

- O serviço `caddy` no `docker-compose.yml` deste projeto está **comentado** —
  **não suba** junto com o central (conflito na porta 443).
- Os arquivos `caddy/Caddyfile`, `caddy/data` e `caddy/config` ficam aqui apenas
  para **referência/rollback**.

## Como adicionar OUTRAS aplicações ao Caddy

Veja o manual completo no proxy central:

**`/srv/docker/caddy/README.md`**

Lá está o passo a passo para publicar uma app por **subdomínio** (preferido,
quando há DNS) ou por **porta específica** (`https://200.136.209.229:8443`),
incluindo reload sem downtime, casos de SSE/WebSocket/upload, extração da CA raiz
e a migração futura para Let's Encrypt.
