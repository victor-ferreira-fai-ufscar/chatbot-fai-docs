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
import unicodedata
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
        best = _match_cited(cited_hint, names)
        if best:
            return best
    return names[0]


def _stem_tokens(name: str) -> set:
    # Sem acento (NFKD->ascii) p/ 'área' casar com o objeto sanitizado 'Area' do bucket.
    stem = PurePosixPath(name).stem.lower()
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    return {t for t in re.split(r"[^a-z0-9]+", stem) if t}


def _match_cited(cited: str, known_names: list[str]) -> Optional[str]:
    """Manual REAL de maior sobreposicao de tokens com o nome citado (>=0.5), ou None.

    Base do casamento = tokens do nome CITADO (fracao deles presente no candidato). Com
    varios manuais, escolhe por citacao qual e o de origem — o token discriminante
    ('sistema'/'area' vs 'dos') desempata. None quando nenhum passa 0.5, para NUNCA
    chutar o manual errado (o chamador entao mantem so a pagina)."""
    hint = _stem_tokens(cited)
    if not hint:
        return None
    best, score = None, 0.0
    for n in known_names:
        s = _overlap(hint, _stem_tokens(n))
        if s > score:
            best, score = n, s
    return best if score >= 0.5 else None


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


def normalize_source_citations(text: str, canonical: Optional[str], page_shift: int = 0,
                               known_names: Optional[list] = None,
                               retrieved_pages: Optional[dict] = None) -> str:
    """Reescreve toda citacao '[arquivo, pag. N]' do texto.

    - Com `known_names` (MULTI-DOC): resolve o nome POR CITACAO — casa o arquivo citado
      com o manual real de origem (>=0.5 de sobreposicao de tokens). Sem match confiavel,
      mantem so a pagina (nunca chuta o manual errado). Tem PRECEDENCIA sobre `canonical`.
      Necessario porque, com 2+ manuais, um `canonical` unico colapsaria TODAS as citacoes
      no mesmo arquivo (misatribuindo a fonte no corpo da resposta).
    - Com `canonical` (doc unico): troca o nome do arquivo pelo canonico, preservando a pagina.
    - Sem nenhum: remove o nome (mantem so a pagina, ou descarta a citacao vazia).
    - `page_shift`: desloca os numeros de pagina (ex.: +1 quando o rodape do PDF marca o
      FIM da pagina e o trecho citado e da pagina seguinte). Mantem a citacao INLINE
      consistente com a pagina exibida nos cards.
    - `retrieved_pages` ({nome_display -> set de paginas RECUPERADAS neste turno}):
      valida cada par (manual, paginas) citado contra o que a recuperacao de fato
      devolveu — ver _validate_pair. Nunca exibe par fabricado.
    """
    if not text or "[" not in text:
        return text

    def repl(m: re.Match) -> str:
        page = (m.group(2) or "").strip()
        if page_shift and page:
            page = re.sub(r"\d+", lambda d: str(int(d.group()) + page_shift), page)
        # Multi-doc: o nome sai da resolucao por citacao (o citado e a dica); doc unico
        # usa o canonico fixo. None nos dois casos -> so a pagina (nunca nome fabricado/errado).
        name = _match_cited(m.group(1) or "", known_names) if known_names else canonical
        if name and page and retrieved_pages:
            name, page = _validate_pair(name, page, retrieved_pages)
        if name:
            return f"[{name}, {page}]" if page else f"[{name}]"
        return f"({page})" if page else ""

    return _CITE_RE.sub(repl, text)


def _validate_pair(name: str, page: str, retrieved: dict) -> tuple:
    """Valida o par (manual, paginas) citado contra o que a RECUPERACAO devolveu no turno.

    Politica conservadora, so age com evidencia:
    - So julga se ha paginas citadas E o manual citado tem paginas conhecidas no mapa
      (card sem numero de pagina nao pune — mapa incompleto passa reto).
    - Alguma pagina citada foi recuperada sob o manual citado -> par plausivel, mantem.
    - NENHUMA pagina bate e ha exatamente UM outro manual que recuperou TODAS elas ->
      etiqueta trocada (padrao PRO-04 da bateria): corrige o nome do manual.
    - Sem candidato inequivoco -> mantem o manual e REMOVE as paginas (nunca exibir
      um par (manual, pagina) que a recuperacao nao sustenta)."""
    nums = [int(x) for x in re.findall(r"\d+", page)]
    allowed = retrieved.get(name)
    if not nums or not allowed:
        return name, page
    if any(n in allowed for n in nums):
        return name, page
    candidates = [m for m, pp in retrieved.items()
                  if m != name and pp and all(n in pp for n in nums)]
    if len(candidates) == 1:
        return candidates[0], page
    return name, ""


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
    # page_shift desloca a(s) pagina(s) preservando o resto (off-by-one do rodape)
    assert normalize_source_citations("> Fonte: [x.pdf, pág. 14]", CANON, page_shift=1) == \
        "> Fonte: [Manual_dos_Coordenadores.pdf, pág. 15]"
    assert normalize_source_citations("> Fonte: [x.pdf, págs. 4-6, 9]", CANON, page_shift=1) == \
        "> Fonte: [Manual_dos_Coordenadores.pdf, págs. 5-7, 10]"
    # canonical picker
    assert canonical_manual_name(["Manual_dos_Coordenadores.pdf"]) == "Manual_dos_Coordenadores.pdf"
    assert canonical_manual_name([]) is None
    assert canonical_manual_name(["A_manual.pdf", "Manual_dos_Coordenadores.pdf"],
                                 "manual coordenador") == "Manual_dos_Coordenadores.pdf"

    # --- MULTI-DOC: resolucao POR CITACAO (nao colapsa tudo no primeiro manual) ---
    MANS = ["Manual do Sistema Area Coordenadores.pdf", "Manual dos Coordenadores.pdf"]
    # citacao de cada manual PERMANECE nele (com e sem acento no citado)
    assert normalize_source_citations("> Fonte: [Manual dos Coordenadores.pdf, pág. 12]", None, known_names=MANS) == \
        "> Fonte: [Manual dos Coordenadores.pdf, pág. 12]"
    assert normalize_source_citations("> Fonte: [Manual do Sistema Área Coordenadores.pdf, pág. 5]", None, known_names=MANS) == \
        "> Fonte: [Manual do Sistema Area Coordenadores.pdf, pág. 5]"
    # duas citacoes distintas no MESMO texto -> cada uma preserva seu arquivo
    assert normalize_source_citations(
        "Veja [Manual dos Coordenadores.pdf, pág. 3] e [Manual do Sistema Área Coordenadores.pdf, pág. 8].",
        None, known_names=MANS,
    ) == "Veja [Manual dos Coordenadores.pdf, pág. 3] e [Manual do Sistema Area Coordenadores.pdf, pág. 8]."
    # nome fabricado sem sobreposicao confiavel -> so a pagina (nunca chuta um dos manuais)
    assert normalize_source_citations("> Fonte: [documento_aleatorio_xyz.pdf, pág. 9]", None, known_names=MANS) == \
        "> Fonte: (pág. 9)"
    # _match_cited: match confiavel vs ausencia de match
    assert _match_cited("Manual do Sistema Area Coordenadores.pdf", MANS) == "Manual do Sistema Area Coordenadores.pdf"
    assert _match_cited("relatorio financeiro anual.pdf", MANS) is None

    # --- VALIDACAO (manual, pagina) x RECUPERADO (retrieved_pages) ---
    RET = {"Manual dos Coordenadores.pdf": {15, 19, 59},
           "Manual do Sistema Area Coordenadores.pdf": {38, 39}}
    # par plausivel (pagina recuperada sob o manual citado) -> intacto
    assert normalize_source_citations("> Fonte: [Manual dos Coordenadores.pdf, pág. 59]",
                                      None, known_names=MANS, retrieved_pages=RET) == \
        "> Fonte: [Manual dos Coordenadores.pdf, pág. 59]"
    # etiqueta trocada (padrao PRO-04): paginas 38-39 so existem sob o manual do sistema -> corrige o nome
    assert normalize_source_citations("> Fonte: [Manual dos Coordenadores.pdf, págs. 38, 39]",
                                      None, known_names=MANS, retrieved_pages=RET) == \
        "> Fonte: [Manual do Sistema Area Coordenadores.pdf, págs. 38, 39]"
    # pagina fabricada (nao recuperada em lugar nenhum) -> mantem o manual, remove a pagina
    assert normalize_source_citations("> Fonte: [Manual dos Coordenadores.pdf, pág. 99]",
                                      None, known_names=MANS, retrieved_pages=RET) == \
        "> Fonte: [Manual dos Coordenadores.pdf]"
    # manual citado SEM paginas no mapa (card sem numero) -> nao pune, passa reto
    RET2 = {"Manual dos Coordenadores.pdf": set(), "Manual do Sistema Area Coordenadores.pdf": {4}}
    assert normalize_source_citations("> Fonte: [Manual dos Coordenadores.pdf, pág. 12]",
                                      None, known_names=MANS, retrieved_pages=RET2) == \
        "> Fonte: [Manual dos Coordenadores.pdf, pág. 12]"
    # mapa vazio (fluxo legado / sem cards) -> comportamento identico ao sem validacao
    assert normalize_source_citations("> Fonte: [Manual dos Coordenadores.pdf, pág. 12]",
                                      None, known_names=MANS, retrieved_pages={}) == \
        "> Fonte: [Manual dos Coordenadores.pdf, pág. 12]"
    print("OK: source_citation self-check passou")
