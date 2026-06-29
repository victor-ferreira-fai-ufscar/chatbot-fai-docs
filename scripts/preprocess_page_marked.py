#!/usr/bin/env python3
"""Pre-processamento page-aware do manual para indexacao no LightRAG.

Extrai o texto PAGINA A PAGINA (fitz/PyMuPDF) e insere um marcador `[PÁGINA N]` no
INICIO de cada pagina, removendo os numeros de rodape soltos do corpo. Isso elimina o
off-by-one de pagina na ORIGEM: o conteudo que segue um marcador e da pagina N. (Antes,
o rodape solto ficava no FIM de cada pagina, exigindo a heuristica de +1; ver
_marker_pages em lightrag_service.py.)

Uso:
    python scripts/preprocess_page_marked.py ENTRADA.pdf SAIDA.txt

Numeracao: no Manual dos Coordenadores (73 paginas) o numero IMPRESSO == indice fisico
+ 1, entao usamos i+1 como N (a capa/sumario inicial nao tem numero impresso, mas a
ordem fisica nao desloca: a pag. fisica 46 imprime "46"). Se trocar de PDF, recalibre
conferindo 2-3 paginas (numero impresso vs ordem fisica).

Indexar depois: POST /documents/text com {text: SAIDA.txt, file_source: "Manual dos
Coordenadores.pdf"} no LightRAG; o backend le os marcadores via _marker_pages.

Usa PyMuPDF (fitz), a mesma stack de PDF do projeto (pymupdf4llm em pdfs.py); pypdf
NAO esta instalado no ambiente. Disponivel no container fai_chatbot_backend, onde
docs/ e bind-mount em /app/docs.
"""
import re
import sys

import fitz  # PyMuPDF

# Numero de rodape solto (numero isolado numa linha) a remover do corpo, para nao
# virar ruido nem competir com o marcador [PÁGINA N].
ISO = re.compile(r"^[ \t]*\d{1,3}[ \t]*$")


def page_marked(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    parts = []
    for i, page in enumerate(doc):
        txt = page.get_text() or ""
        body = "\n".join(l for l in txt.splitlines() if not ISO.match(l)).strip()
        parts.append(f"[PÁGINA {i + 1}]\n{body}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    out = page_marked(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    print(f"OK: {sys.argv[2]} ({len(out)} chars, {out.count('[PÁGINA')} marcadores)")
