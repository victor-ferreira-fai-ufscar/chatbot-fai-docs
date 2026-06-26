"""Guard determinístico anti-alucinação de REFERÊNCIA LEGAL.

O modelo de síntese às vezes anexa "base legal" de memória (ex.: ISS — Lei Complementar
nº 116/2003) que NÃO consta no Manual do Coordenador. Este filtro de streaming descarta
qualquer FRASE que cite o número de uma Lei/Decreto/Resolução cujo NÚMERO-BASE (a parte
antes do "/ano") não exista no manual indexado.

Importante: casa pelo número-base, então MANTÉM leis que o manual realmente referencia
mesmo que o modelo acrescente o ano. Ex.: o manual cita "Lei nº 5.452" (CLT); o modelo
escreve "Decreto-Lei nº 5.452/1943" -> base "5.452" está no manual -> MANTÉM. Já a ISS
"116/2003" (base "116") não está no manual -> a frase que a cita é DESCARTADA.

Sem dependências externas (só `re`) na lógica pura, para ser testável isoladamente.
"""
from __future__ import annotations

import re

# Palavra de norma seguida (até ~45 chars) do número-base (grupos de dígitos com pontos)
# e de um "/ano" opcional. Captura o número-base no grupo 1.
_LEGAL_CITE = re.compile(
    r"(?:Lei(?:\s+Complementar)?|Decreto(?:[-\s]?Lei)?|Resolu[çc][ãa]o|Portaria|"
    r"Instru[çc][ãa]o\s+Normativa|Medida\s+Provis[óo]ria)"
    r"[^.;:\n]{0,45}?(\d{1,4}(?:\.\d{1,3})*)\s*(?:/\s*\d{2,4})?",
    re.I,
)

# Conjunto de fallback: números-base de norma do Manual do Coordenador (06-05), caso a
# extração dinâmica do PDF do bucket falhe. Mantém o guard funcional offline.
# Números-base verificados no manual (incl. ISS "116 de 2003", CLT "5.452", C.Civil "10.406").
_FALLBACK_ALLOWED = {
    "022", "22", "013", "12", "13", "116", "448", "5.452", "10.406", "11.788",
    "13.243", "14.133", "5.194", "63.911", "7.423", "8.241", "8.948", "8.958", "9.283",
}

_ALLOWED_CACHE: set | None = None


def law_numbers_in(text: str) -> set:
    """Números-base de norma citados em `text` (parte antes do /ano)."""
    return {m.group(1).replace(" ", "") for m in _LEGAL_CITE.finditer(text or "")}


def manual_law_numbers(storage=None, page_extractor=None) -> set:
    """Allowlist = números-base de norma presentes nos PDFs de manual do bucket.

    Cacheada (extrai uma vez). `storage` é um StorageService; `page_extractor(bytes)->{pág:texto}`
    (tipicamente pdf_pages._extract_pages). Em qualquer falha, usa o fallback verificado.
    """
    global _ALLOWED_CACHE
    if _ALLOWED_CACHE is not None:
        return _ALLOWED_CACHE
    allowed = set(_FALLBACK_ALLOWED)
    try:
        if storage is not None and page_extractor is not None:
            for obj in storage.list_objects(limit=100):
                name = obj.get("name", "")
                if name.lower().endswith(".pdf"):
                    pages = page_extractor(storage.download(name))
                    allowed |= law_numbers_in(" ".join(pages.values()))
    except Exception:
        pass  # mantém o fallback
    _ALLOWED_CACHE = allowed
    return allowed


class LegalRefGuard:
    """Filtro de streaming: remove frases que citem norma com número fora do allowlist.

    Uso: `guard.feed(chunk)` retorna o texto já limpo das frases COMPLETAS vistas até
    agora (bufferiza a frase incompleta); ao final, `guard.flush()` devolve o resto.
    """

    # Fim de frase: pontuação seguida de espaço (não quebra dentro de "5.452") ou nova linha.
    _BOUNDARY = re.compile(r"[.!?;](?=\s)|\n")

    def __init__(self, allowed: set | None):
        self.allowed = allowed or set()
        self._buf = ""

    def _clean(self, sentence: str) -> str:
        nums = law_numbers_in(sentence)
        if nums and any(n not in self.allowed for n in nums):
            return ""  # cita norma com número ausente no manual -> descarta a frase
        return sentence

    def feed(self, chunk: str) -> str:
        self._buf += chunk or ""
        out = []
        search_from = 0
        while True:
            m = self._BOUNDARY.search(self._buf, search_from)
            if not m:
                break
            cut = m.end()
            # NAO cortar DENTRO de uma citacao '[...]' aberta. O ponto de "pág."/"págs."
            # cai num boundary e partiria a citacao ao meio (ex.: "[Arquivo.pdf, págs." | " 38]"),
            # impedindo a normalizacao do nome do arquivo (normalize_source_citations exige o
            # '[...]' inteiro). Pula este boundary e busca o proximo APOS o fechamento ']'.
            if self._buf.count("[", 0, cut) > self._buf.count("]", 0, cut):
                search_from = cut
                continue
            sentence, self._buf = self._buf[:cut], self._buf[cut:]
            out.append(self._clean(sentence))
            search_from = 0
        return "".join(out)

    def flush(self) -> str:
        rest, self._buf = self._buf, ""
        return self._clean(rest) if rest else ""
