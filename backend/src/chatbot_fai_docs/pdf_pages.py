"""Extracao de texto por PAGINA (layout-aware) de um PDF, para a sidebar de fontes.

Reaproveita a MESMA estrategia da re-indexacao do Manual do Coordenador: o PDF tem
layout de 2 colunas com um menu de navegacao lateral que "vaza" no texto. Filtramos
por coordenada x (descarta o menu lateral e o cabecalho) e ordenamos por coluna
(esquerda, depois direita) para reconstruir a ordem de leitura. A pagina retornada
e indexada por numero exibido (= indice do PDF + 1 = ancora #page=N do navegador),
entao casa exatamente com a pagina citada nas fontes e com o PDF aberto pelo usuario.

O resultado e cacheado em memoria por nome de objeto (o PDF muda raramente).
"""
from __future__ import annotations

import re
from typing import Callable

import fitz  # PyMuPDF

_PAGE_NUM_RE = re.compile(r"^\d{1,3}$")
_NAV_MAX_X = 160      # blocos com x0 < 160 = menu lateral/cabecalho -> descartar
_COL_SPLIT = 430      # x0 < 430 = coluna esquerda do corpo; >= 430 = coluna direita

# Cache: nome_do_objeto -> {pagina(int): texto(str)}
_CACHE: dict[str, dict[int, str]] = {}


def _extract_pages(pdf_bytes: bytes) -> dict[int, str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: dict[int, str] = {}
    for idx in range(doc.page_count):
        page = doc[idx]
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, blockno, type)
        # menu lateral presente? varios blocos colados na margem esquerda
        n_left = sum(1 for b in blocks if 13 <= b[0] <= 18 and " ".join(b[4].split()))
        has_nav = n_left >= 5
        body: list[tuple] = []
        for b in blocks:
            x0, y0, txt = b[0], b[1], b[4]
            s = " ".join(txt.split())
            if not s:
                continue
            # numero de pagina no topo-direito (paginacao do PDF) -> ignora
            if y0 < 35 and x0 > 680 and _PAGE_NUM_RE.match(s):
                continue
            if has_nav and x0 < _NAV_MAX_X:  # menu lateral + cabecalho
                continue
            body.append((0 if x0 < _COL_SPLIT else 1, round(y0, 1), x0, s))
        body.sort(key=lambda t: (t[0], t[1], t[2]))  # coluna esq (por y), depois dir
        pages[idx + 1] = " ".join(s for _, _, _, s in body)
    doc.close()
    return pages


def get_page_text(object_name: str, page: int, loader: Callable[[], bytes]) -> str:
    """Texto limpo da `page` (1-based) do PDF identificado por `object_name`.

    `loader` e chamado (uma unica vez por objeto, depois cacheia) para obter os
    bytes do PDF — tipicamente um download do bucket. Retorna "" se a pagina nao
    existir.
    """
    if object_name not in _CACHE:
        _CACHE[object_name] = _extract_pages(loader())
    return _CACHE[object_name].get(int(page), "")


def clear_cache(object_name: str | None = None) -> None:
    """Invalida o cache (de um objeto, ou todo). Util apos re-upload de um manual."""
    if object_name is None:
        _CACHE.clear()
    else:
        _CACHE.pop(object_name, None)
