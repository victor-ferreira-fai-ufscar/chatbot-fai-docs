"""Normalizacao deterministica das citacoes de fonte no TEXTO da resposta.

O modelo, seguindo a regra de "citar a fonte", costuma escrever o nome do arquivo
ERRADO no corpo da resposta (ex.: '> Fonte: [M-coordenadoresFAI-01-06_1.pdf]'),
um nome que NAO corresponde a nenhum documento real — porque a lista de manuais
chegava vazia e/ou ele extrai um codigo interno do proprio PDF. Isso gera "fontes
que nao existem" e quebra a sidebar ("trecho indisponivel").

Aqui reescrevemos qualquer nome de arquivo citado entre colchetes para o nome
CANONICO do manual (derivado dos documentos reais do bucket), preservando a pagina.
Se nao houver um nome canonico (ex.: bucket indisponivel), removemos o nome e
mantemos apenas a pagina — nunca deixamos passar um nome fabricado.

Funciona sobre texto ja "fechado" (frases completas), entao integra com o
LegalRefGuard, que ja entrega o texto em fronteiras de frase (a citacao
'[arquivo.pdf, pag. N]' nunca e partida no meio).
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Optional

# [ qualquer-coisa.pdf  (, ; - espaco)  (pag./pags. N[, M-O]) ]  -> grupos: arquivo, pagina(opcional)
_CITE_RE = re.compile(
    r"\[\s*([^\[\]]*?\.(?:pdf|docx?|txt|md))\s*(?:[,;\-\s]+\s*(p[áa]gs?\.?\s*\d[\d\s,\-]*?))?\s*\]",
    re.I,
)


def canonical_manual_name(known_names: list[str], cited_hint: Optional[str] = None) -> Optional[str]:
    """Escolhe o nome canonico a exibir nas citacoes a partir dos documentos REAIS.

    Caso comum (um unico manual): retorna esse nome. Com varios, tenta casar com a
    dica citada (best-effort) e, na duvida, retorna o primeiro. Retorna None se nao
    houver nenhum documento conhecido.
    """
    names = [n for n in (known_names or []) if n]
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    if cited_hint:
        hint = _stem_tokens(cited_hint)
        best, score = None, 0.0
        for n in names:
            s = _overlap(hint, _stem_tokens(n))
            if s > score:
                best, score = n, s
        if best and score >= 0.5:
            return best
    return names[0]


def _stem_tokens(name: str) -> set:
    stem = PurePosixPath(name).stem.lower()
    return {t for t in re.split(r"[^a-z0-9]+", stem) if t}


def _overlap(a: set, b: set) -> float:
    """Fração dos tokens de `a` presentes em `b`, casando por prefixo >=4 chars
    (tolerante a singular/plural: 'coordenador' ~ 'coordenadores')."""
    if not a:
        return 0.0
    def hit(t: str) -> bool:
        return any(t == u or (min(len(t), len(u)) >= 4 and (t.startswith(u) or u.startswith(t))) for u in b)
    return sum(1 for t in a if hit(t)) / len(a)


_SOURCE_LINE_RE = re.compile(r"^(\s*-\s*)(.+?)(\s*\(p[áa]gs?\.[^)]*\))?\s*$", re.I)


def canonicalize_source_line(line: str, canonical: Optional[str]) -> str:
    """Troca o nome do arquivo numa linha de fonte ('- <nome> (págs. N)') pelo nome
    canonico, preservando o rotulo de paginas. Mantem a linha intacta se nao casar
    ou se nao houver canonico. Usado para o nome do CARD bater com a citacao do texto."""
    if not canonical or not line:
        return line
    m = _SOURCE_LINE_RE.match(line)
    if not m:
        return line
    pages = m.group(3) or ""
    return f"{m.group(1)}{canonical}{pages}"


def normalize_source_citations(text: str, canonical: Optional[str]) -> str:
    """Reescreve toda citacao '[arquivo, pag. N]' do texto.

    - Com `canonical`: troca o nome do arquivo pelo canonico, preservando a pagina.
    - Sem `canonical`: remove o nome (mantem so a pagina, ou descarta a citacao vazia).
    """
    if not text or "[" not in text:
        return text

    def repl(m: re.Match) -> str:
        page = (m.group(2) or "").strip()
        if canonical:
            return f"[{canonical}, {page}]" if page else f"[{canonical}]"
        # Sem nome canonico: nunca exibir nome fabricado -> so a pagina.
        return f"({page})" if page else ""

    return _CITE_RE.sub(repl, text)


# --------------------------------------------------------------------- self-check
if __name__ == "__main__":
    CANON = "Manual_dos_Coordenadores.pdf"
    # nome fabricado + pagina -> canonico + pagina
    assert normalize_source_citations(
        "Texto. > Fonte: [M-coordenadoresFAI-01-06_1.pdf, pág. 12]", CANON
    ) == "Texto. > Fonte: [Manual_dos_Coordenadores.pdf, pág. 12]"
    # sem pagina
    assert normalize_source_citations("> Fonte: [Manual_Coordenadores.pdf]", CANON) == \
        "> Fonte: [Manual_dos_Coordenadores.pdf]"
    # citacao inline no meio da frase
    assert normalize_source_citations("conforme [algo.pdf, págs. 4-6] previsto", CANON) == \
        "conforme [Manual_dos_Coordenadores.pdf, págs. 4-6] previsto"
    # sem canonico -> mantem so a pagina (nunca nome fabricado)
    assert normalize_source_citations("> Fonte: [x.pdf, pág. 9]", None) == "> Fonte: (pág. 9)"
    assert normalize_source_citations("> Fonte: [x.pdf]", None) == "> Fonte: "
    # canonicalizacao da linha de fonte (card)
    assert canonicalize_source_line("- Manual do Coordenador.pdf (pág. 8)", "Manual dos Coordenadores.pdf") == \
        "- Manual dos Coordenadores.pdf (pág. 8)"
    assert canonicalize_source_line("- Manual do Coordenador.pdf", "Manual dos Coordenadores.pdf") == \
        "- Manual dos Coordenadores.pdf"
    assert canonicalize_source_line("- X.pdf (pág. 8)", None) == "- X.pdf (pág. 8)"
    # texto sem citacao passa intacto
    assert normalize_source_citations("sem fonte aqui", CANON) == "sem fonte aqui"
    # canonical picker
    assert canonical_manual_name(["Manual_dos_Coordenadores.pdf"]) == "Manual_dos_Coordenadores.pdf"
    assert canonical_manual_name([]) is None
    assert canonical_manual_name(["A_manual.pdf", "Manual_dos_Coordenadores.pdf"],
                                 "manual coordenador") == "Manual_dos_Coordenadores.pdf"
    print("OK: source_citation self-check passou")
