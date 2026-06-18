"""Skill gerar_documento_pdf: converte Markdown -> HTML -> PDF (WeasyPrint) com um
CSS institucional, sobe ao Storage e devolve um link de download assinado.

A funcao `_build_pdf_bytes` e PURA (sem dependencia do Storage nem dos tipos do
agente) para permitir teste isolado; `markdown` e `weasyprint` sao importados de
forma preguicosa (so quando gera o PDF), entao o modulo carrega so com stdlib.
"""
import html as _html

# CSS institucional: A4 com margens, cabecalho com o titulo na 1a pagina e rodape
# (texto opcional + numero da pagina) em todas. Fontes seguras (DejaVu) instaladas
# na imagem para renderizar acentuacao corretamente offline.
_CSS = """
@page {{
  size: A4;
  margin: 2.2cm 2cm 2.4cm 2cm;
  @bottom-center {{
    content: "{rodape}";
    font-family: "DejaVu Sans", sans-serif;
    font-size: 8pt;
    color: #666;
  }}
  @bottom-right {{
    content: "pag. " counter(page) " / " counter(pages);
    font-family: "DejaVu Sans", sans-serif;
    font-size: 8pt;
    color: #666;
  }}
}}
body {{
  font-family: "DejaVu Serif", serif;
  font-size: 11pt;
  line-height: 1.5;
  color: #1a1a1a;
}}
h1.doc-title {{
  font-family: "DejaVu Sans", sans-serif;
  font-size: 18pt;
  color: #0b3d2e;
  border-bottom: 2px solid #0b3d2e;
  padding-bottom: 6px;
  margin: 0 0 18px 0;
}}
h2, h3 {{ font-family: "DejaVu Sans", sans-serif; color: #0b3d2e; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #bbb; padding: 5px 8px; text-align: left; font-size: 10pt; }}
th {{ background: #eef3f1; }}
code {{ font-family: "DejaVu Sans Mono", monospace; font-size: 10pt; }}
"""


def _build_pdf_bytes(titulo: str, conteudo_markdown: str, rodape: str = "") -> bytes:
    import markdown as _md  # import preguicoso (dependencia pesada)
    from weasyprint import HTML

    corpo_html = _md.markdown(
        conteudo_markdown or "",
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    titulo_safe = _html.escape(titulo or "Documento")
    # rodape vai dentro de content: "..." do CSS -> escapa aspas duplas
    rodape_css = (rodape or "").replace("\\", "").replace('"', "'")
    css = _CSS.format(rodape=rodape_css)
    doc_html = (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{css}</style></head><body>"
        f"<h1 class='doc-title'>{titulo_safe}</h1>{corpo_html}</body></html>"
    )
    return HTML(string=doc_html).write_pdf()


def executar(args: dict, ctx) -> "object":
    from src.chatbot_fai_docs.agent.types import SkillResult

    titulo = (args.get("titulo") or "").strip()
    conteudo = args.get("conteudo_markdown") or ""
    rodape = (args.get("rodape") or "").strip()

    if not titulo or not conteudo.strip():
        return SkillResult(
            for_model="Erro: gerar_documento_pdf requer 'titulo' e 'conteudo_markdown'.",
            error=True,
        )
    # Documentos GERADOS vao para o bucket temporario (separado dos manuais).
    storage = ctx.temp_storage or ctx.storage
    if storage is None:
        return SkillResult(
            for_model="Erro: armazenamento (Storage) indisponivel para entregar o PDF.",
            error=True,
        )

    try:
        conteudo_pdf = _build_pdf_bytes(titulo, conteudo, rodape)
    except Exception as e:  # noqa: BLE001 - erro de geracao vira mensagem p/ o modelo
        return SkillResult(for_model=f"Erro ao montar o PDF: {e}", error=True)

    nome = storage.sanitize_object_name(titulo) + ".pdf"
    try:
        storage.upload(nome, conteudo_pdf, content_type="application/pdf")
        url = storage.create_signed_url(nome, expires_in=ctx.signed_url_ttl)
    except Exception as e:  # noqa: BLE001
        return SkillResult(for_model=f"Erro ao salvar/entregar o PDF: {e}", error=True)

    return SkillResult(
        for_model=(
            f"Documento PDF '{nome}' gerado ({len(conteudo_pdf)} bytes). O link de "
            f"download sera anexado automaticamente a resposta."
        ),
        downloads=[(nome, url)],
    )
