"""Exportacao de uma conversa para PDF branded (FAI-UFSCar) via WeasyPrint.

Espelha o layout aprovado no mockup: cabecalho institucional (icone FAI + wordmark
+ data de exportacao), titulo da conversa, transcricao em blocos Pergunta/Lina com
markdown e chips de Fontes, e rodape (aviso + numeracao) repetido em todas as paginas
via @page.

`build_conversation_pdf` recebe os MessageRecord do repositorio (tem .role, .content,
.metadata). markdown/weasyprint sao importados de forma PREGUICOSA (dependencias
pesadas) para o modulo carregar so com stdlib. As fontes DejaVu vem instaladas na
imagem (fonts-dejavu-core) -> acentuacao correta offline.
"""
from __future__ import annotations

import base64
import html as _html
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# Icone FAI (o quadrado colorido) embutido como data URI no cabecalho.
_ICON_PATH = Path(__file__).resolve().parent / "assets" / "fai-icone.png"

_MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

# Linha "> Fonte: [...]" que o modelo escreve no corpo: removida do corpo porque as
# fontes sao renderizadas separadamente como chips (a partir de metadata["sources"]).
_FONTE_LINE_RE = re.compile(r"(?im)^[ \t]*>?[ \t]*fonte:.*$")

# Allowlist de tags do HTML da RESPOSTA (o que o markdown legitimamente produz).
# Tudo fora disso e' removido pelo sanitizador -> injecao de <style>/style= (que
# reposicionaria/esconderia elementos e sobreporia o aviso do rodape) e' neutralizada.
_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "b", "i", "u", "s", "code", "pre", "blockquote",
    "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
    "table", "thead", "tbody", "tr", "th", "td", "a", "sup", "sub",
}
_ALLOWED_ATTRS = {"a": {"href", "title"}}


def _icon_data_uri() -> str:
    try:
        raw = _ICON_PATH.read_bytes()
        return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    except Exception:
        return ""  # sem icone (degrada para so o wordmark) em vez de quebrar o PDF


def _fmt_data_pt(dt: datetime) -> str:
    return f"{dt.day} de {_MESES_PT[dt.month - 1]} de {dt.year}"


def _clean_source_line(line: str) -> str:
    """"- Manual do Coordenador.pdf (pág. 12)" -> "Manual do Coordenador.pdf · pág. 12"."""
    s = (line or "").strip()
    s = re.sub(r"^-\s*", "", s)
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", s)
    if m:
        nome, pag = m.group(1).strip(), m.group(2).strip()
        # remove eventual relevancia "· 98%" do rotulo de pagina
        pag = re.sub(r"\s*·\s*\d{1,3}\s*%", "", pag).strip()
        return f"{_html.escape(nome)} <span class='pg'>· {_html.escape(pag)}</span>"
    return _html.escape(s)


def _render_answer_html(content: str) -> str:
    import markdown as _md  # import preguicoso
    import nh3

    corpo = _FONTE_LINE_RE.sub("", content or "").strip()
    rendered = _md.markdown(corpo, extensions=["tables", "fenced_code", "sane_lists"])
    # SANITIZA: a resposta e' gerada pelo modelo. Sem allowlist, um <style>/style=
    # embutido injetaria CSS no PDF (esconder cabecalho/aviso, overlay opaco).
    return nh3.clean(rendered, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS)


def _sources_html(sources: Any) -> str:
    if not sources or not isinstance(sources, (list, tuple)):
        return ""
    chips = "".join(f"<span class='chip'>{_clean_source_line(s)}</span>" for s in sources if s)
    if not chips:
        return ""
    return f"<div class='sources'><span class='lbl'>Fontes</span>{chips}</div>"


def _turn_html(role: str, content: str, metadata: dict) -> str:
    if role == "user":
        return (
            "<div class='turn'>"
            "<div class='eyebrow q'><span class='dot'></span>Pergunta</div>"
            f"<div class='question'>{_html.escape(content or '')}</div>"
            "</div>"
        )
    # assistant
    icon = _icon_data_uri()
    icon_img = f"<img alt='' src='{icon}'>" if icon else ""
    return (
        "<div class='turn'>"
        f"<div class='eyebrow a'>{icon_img}Lina · Assistente Virtual</div>"
        f"<div class='answer'>{_render_answer_html(content)}</div>"
        f"{_sources_html((metadata or {}).get('sources'))}"
        "</div>"
    )


def _build_css() -> str:
    return """
@page {
  size: A4;
  margin: 2cm 1.8cm 2.2cm 1.8cm;
  @bottom-left {
    content: "FAI-UFSCar · Assistente Virtual Lina · confira sempre as fontes citadas";
    font-family: "DejaVu Sans", sans-serif; font-size: 7pt; color: #8a97a3;
  }
  @bottom-right {
    content: "pág. " counter(page) " / " counter(pages);
    font-family: "DejaVu Sans", sans-serif; font-size: 8pt; color: #8a97a3;
  }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 10.5pt; line-height: 1.55; color: #1f2937; margin: 0; }

/* Cabecalho (tabela p/ robustez no WeasyPrint) */
table.head { width: 100%; border-collapse: collapse; }
table.head td { border: none; padding: 0; vertical-align: bottom; }
.brand-cell img { width: 26pt; height: 26pt; vertical-align: middle; }
.brand-cell .word { font-size: 15pt; font-weight: bold; color: #204d74; vertical-align: middle; margin-left: 7pt; }
.brand-cell .word span { font-weight: normal; color: #5b7083; }
.brand-cell .sub { font-size: 7pt; letter-spacing: 1.2pt; text-transform: uppercase; color: #5b7083; margin-top: 4pt; }
.meta-cell { text-align: right; }
.meta-cell .k { font-size: 6.5pt; letter-spacing: 1.2pt; text-transform: uppercase; color: #5b7083; }
.meta-cell .v { font-size: 9pt; color: #1f2937; }
.rule { height: 2pt; background: #367fa9; margin-top: 9pt; }

/* Titulo do documento */
.title { margin-top: 20pt; }
.title h1 { font-size: 16pt; line-height: 1.25; color: #204d74; margin: 0 0 8pt; padding-bottom: 8pt; border-bottom: 0.75pt solid #d7e2ea; }
.title .docmeta { font-size: 9pt; color: #5b7083; }
.title .docmeta b { color: #1f2937; }

/* Transcricao */
.turn { margin-top: 16pt; }
.turn + .turn { border-top: 0.75pt dashed #d7e2ea; padding-top: 16pt; }
.eyebrow { font-size: 8pt; letter-spacing: 1.2pt; text-transform: uppercase; font-weight: bold; margin-bottom: 7pt; break-after: avoid; }
.eyebrow.q { color: #5b7083; }
.eyebrow.a { color: #204d74; }
.eyebrow.q .dot { display: inline-block; width: 5pt; height: 5pt; border-radius: 5pt; background: #5b7083; margin-right: 6pt; vertical-align: middle; }
.eyebrow.a img { width: 12pt; height: 12pt; vertical-align: middle; margin-right: 6pt; }
.question { background: #f0f5f9; border-left: 3pt solid #367fa9; border-radius: 0 4pt 4pt 0; padding: 9pt 12pt; }
.answer p { margin: 0 0 8pt; }
.answer p:last-child { margin-bottom: 0; }
.answer strong { color: #204d74; }
.answer ul, .answer ol { margin: 0 0 8pt; padding-left: 16pt; }
.answer li { margin: 3pt 0; }
.answer table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
.answer th, .answer td { border: 0.75pt solid #cbd6de; padding: 4pt 7pt; text-align: left; font-size: 9.5pt; }
.answer th { background: #eef3f7; }
.answer code { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; }

/* Fontes (chips) */
.sources { margin-top: 10pt; }
.sources .lbl { font-size: 7pt; letter-spacing: 1.2pt; text-transform: uppercase; color: #5b7083; font-weight: bold; margin-right: 6pt; }
.chip { display: inline-block; font-size: 8.5pt; color: #204d74; background: #f0f5f9; border: 0.75pt solid #d7e2ea; border-radius: 20pt; padding: 2pt 9pt; margin: 0 4pt 3pt 0; }
.chip .pg { color: #5b7083; }
"""


def _no_network_url_fetcher(url: str):
    """Bloqueia QUALQUER recurso que não seja data: URI. O corpo das respostas é
    gerado pelo modelo (RAG) e poderia conter `![](http://...)` — sem esta trava o
    WeasyPrint faria requisições de rede (SSRF / travamento). Só o ícone embutido
    (data:) é permitido; recursos externos viram vazio (não quebram o PDF)."""
    from weasyprint import default_url_fetcher

    if url.startswith("data:"):
        return default_url_fetcher(url)
    return {"string": b"", "mime_type": "image/png"}


def build_conversation_pdf(
    title: str,
    messages: list,
    *,
    conversation_id: int,
    exported_at: datetime,
) -> bytes:
    """Monta o PDF branded da conversa. `messages` = MessageRecord (role/content/metadata)."""
    from weasyprint import HTML

    n_perguntas = sum(1 for m in messages if getattr(m, "role", None) == "user")
    turnos = "".join(
        _turn_html(getattr(m, "role", ""), getattr(m, "content", ""), getattr(m, "metadata", {}) or {})
        for m in messages
        if getattr(m, "role", None) in ("user", "assistant") and (getattr(m, "content", "") or "").strip()
    )

    icon = _icon_data_uri()
    header_img = f"<img alt='FAI' src='{icon}'>" if icon else ""
    titulo_safe = _html.escape((title or "Conversa").strip())

    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<style>{_build_css()}</style></head><body>
<table class="head"><tr>
  <td class="brand-cell">
    {header_img}<span class="word">FAI <span>&bull; UFSCar</span></span>
    <div class="sub">Fundação de Apoio Institucional</div>
  </td>
  <td class="meta-cell">
    <div class="k">Exportado em</div>
    <div class="v">{_fmt_data_pt(exported_at)}</div>
  </td>
</tr></table>
<div class="rule"></div>
<div class="title">
  <h1>{titulo_safe}</h1>
  <div class="docmeta">Conversa com a <b>Lina</b> &mdash; Assistente Virtual da FAI-UFSCar
    &nbsp;&middot;&nbsp; {n_perguntas} pergunta{'s' if n_perguntas != 1 else ''}
    &nbsp;&middot;&nbsp; conversa nº {conversation_id}</div>
</div>
{turnos}
</body></html>"""

    return HTML(string=doc, url_fetcher=_no_network_url_fetcher).write_pdf()
