#!/usr/bin/env python3
"""Pre-processamento page-aware do manual para indexacao no LightRAG.

Gera, a partir do PDF, um TXT em que CADA frase carrega um marcador `[PÁGINA N]`
imediatamente antes. O conteudo que segue um marcador e da pagina N -> sem
off-by-one na ORIGEM. Resolve dois problemas do indexador anterior:

1) EXTRACAO layout-aware (reusa `_extract_pages` de pdf_pages.py — o MESMO extrator
   da sidebar de fontes): ordena as 2 colunas na ordem de leitura, descarta o menu
   de navegacao lateral (que se repetia em TODO chunk e diluia o retrieval) e
   recupera corpo que o `get_text()` cru perdia/embaralhava em paginas de 2 colunas.
   Bonus: o texto indexado passa a casar com o que a sidebar exibe (fonte unica).

2) MARCADOR DENSO por frase, nao so 1 no topo da pagina. O LightRAG re-chunkeia por
   tokens (fixed_token, chunk_token_size=1200, overlap=100) e corta no MEIO das
   paginas. Com 1 marcador so no topo, o trecho que caia num chunk SEM ele era
   atribuido a pagina vizinha (off-by-one: ~29% do conteudo mal-rotulado). Repetindo
   o marcador antes de cada frase — e subdividindo frases longas (tabelas/listas) ate
   _CAP_CHARS, mantendo o maior intervalo entre marcadores ABAIXO do overlap de 100
   tokens — todo trecho da pagina N carrega `[PÁGINA N]` em qualquer chunk. A regiao
   orfa de um corte sempre reaparece, ja rotulada, no chunk vizinho via overlap, entao
   nenhuma pagina se "perde" (medido: ~1.9% mal-rotulado, maxgap ~93 < 100). Serve
   tanto ao modelo (Prompt.md: "marcador imediatamente ANTERIOR") quanto ao resolver
   deterministico (_marker_pages em lightrag_service.py).

Uso (rodar ONDE `src.chatbot_fai_docs` e importavel — tipicamente o container backend):
    docker cp scripts/preprocess_page_marked.py fai_chatbot_backend:/tmp/pp.py
    docker exec -w /app -e PYTHONPATH=/app fai_chatbot_backend \
        python3 /tmp/pp.py "/app/docs/manual/<ENTRADA>.pdf" "/app/docs/<SAIDA>.txt"

Numeracao: o marcador N e a pagina 1-based do PDF (= ancora #page=N do navegador =
indice exibido pela sidebar). No Manual dos Coordenadores o rodape impresso bate com
N (pag. fisica i imprime i+1). Se trocar de PDF, recalibre conferindo 2-3 paginas.

Indexar depois: POST /documents/text com {text: SAIDA.txt, file_source: "Manual dos
Coordenadores.pdf"} no LightRAG; o backend le os marcadores via _marker_pages.
"""
import re
import sys

# Mesmo extrator layout-aware da sidebar de fontes (filtra menu lateral, ordena
# colunas). Devolve {pagina 1-based: texto}. Exige o pacote no PYTHONPATH.
from src.chatbot_fai_docs.pdf_pages import _extract_pages

# Tamanho-alvo de cada segmento (chars ~= tokens*4). Mantido ABAIXO do overlap de
# chunk do LightRAG (chunk_overlap_token_size=100 tokens ~= 400 chars) com folga,
# para que o maior intervalo entre dois `[PÁGINA N]` nunca exceda o overlap.
_CAP_CHARS = 280
# Fim de frase = .!?:; seguido de espaco. `_extract_pages` une o corpo com espacos
# (sem quebras), entao a frase e a unidade natural de segmentacao.
_SENT_SPLIT = re.compile(r"(?<=[.!?:;])\s+")


def _cap_long(seg: str, cap: int = _CAP_CHARS) -> list:
    """Subdivide um segmento maior que `cap` em fronteira de palavra. Tabelas/listas
    longas sem pontuacao viram uma 'frase' gigante; sem este cap o intervalo entre
    marcadores estouraria o overlap e reabriria o off-by-one naquele trecho."""
    if len(seg) <= cap:
        return [seg]
    out, cur = [], ""
    for w in seg.split():
        if cur and len(cur) + 1 + len(w) > cap:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def _segments(body: str) -> list:
    """Corpo de uma pagina -> segmentos curtos: por frase, e cada frase longa
    subdividida por palavra ate `_CAP_CHARS`."""
    out = []
    for s in (p.strip() for p in _SENT_SPLIT.split(body) if p.strip()):
        out.extend(_cap_long(s))
    return out


def page_marked(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        pages = _extract_pages(f.read())  # {pagina 1-based: texto layout-aware}
    parts = []
    for p in sorted(pages):
        mark = f"[PÁGINA {p}]"
        segs = _segments((pages[p] or "").strip())
        # Marcador imediatamente ANTES de cada segmento; pagina vazia -> so o marcador.
        block = "\n".join(f"{mark} {s}" for s in segs) if segs else mark
        parts.append(block)
    return "\n\n".join(parts)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    out = page_marked(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    print(f"OK: {sys.argv[2]} ({len(out)} chars, {out.count('[PÁGINA')} marcadores)")
