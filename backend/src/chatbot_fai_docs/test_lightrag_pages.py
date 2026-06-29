"""Testes das funcoes puras de extracao de PAGINA das fontes do LightRAG.

Roda no host, sem rede e sem dependencias pesadas:

    python3 backend/src/chatbot_fai_docs/test_lightrag_pages.py

Importa o modulo isoladamente (sem o __init__ pesado de chatbot_fai_docs, que
puxa openai/sentence-transformers) carregando o arquivo direto por path.
"""
import importlib.util
import sys
import types
from pathlib import Path

# Carrega lightrag_service.py ISOLADO. Suas importacoes de topo
# (src.chatbot_fai_docs.config/utils/pdfs) disparariam o __init__ pesado do
# pacote (openai/sentence-transformers), entao stubamos esses modulos: os
# helpers sob teste so dependem de json/re.
def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod

_stub("src")
_stub("src.chatbot_fai_docs")
_stub("src.chatbot_fai_docs.config", AppConfig=object)
_stub("src.chatbot_fai_docs.utils", get_current_date_time_pt_br=lambda: ("", ""))
_stub("src.chatbot_fai_docs.pdfs", list_pdf_files=lambda *_a, **_k: [])

_mod_path = Path(__file__).resolve().parent / "lightrag_service.py"
_spec = importlib.util.spec_from_file_location("_lrs_under_test", _mod_path)
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)

failures = 0


def check(cond, msg):
    global failures
    status = "ok " if cond else "FALHOU"
    if not cond:
        failures += 1
    print(f"[{status}] {msg}")


# --- _marker_pages: marcadores [PÁGINA N] no inicio de cada pagina ---
content = "[PÁGINA 4]\nmais texto\n[PÁGINA 5]\n[PÁGINA 6]\nlista: 1) item nao conta\nFundacao 2024\n"
check(_m._marker_pages(content) == [4, 5, 6], "_marker_pages pega os marcadores [PÁGINA N]")
check(_m._marker_pages("") == [], "_marker_pages vazio em conteudo vazio")
check(_m._marker_pages("texto sem marcador\n1.2\n5.452\n") == [], "_marker_pages ignora numeros soltos (sem marcador)")

# --- _compact_pages: faixas compactas, unicas e ordenadas ---
check(_m._compact_pages([4, 5, 6, 9]) == "4-6, 9", "_compact_pages junta consecutivos e mantem isolados")
check(_m._compact_pages([7, 5, 6, 5]) == "5-7", "_compact_pages dedup + ordena")
check(_m._compact_pages([]) == "", "_compact_pages vazio")
check(_m._compact_pages([0, -1, 12]) == "12", "_compact_pages descarta nao-positivos")
check(_m._compact_pages([12]) == "12", "_compact_pages pagina unica")

# --- _format_source_line: rotulo pag./pags. e fallback sem pagina ---
check(_m._format_source_line("M.pdf", [12]) == "- M.pdf (pág. 12)", "uma pagina -> 'pág.'")
check(_m._format_source_line("M.pdf", [4, 5, 6]) == "- M.pdf (págs. 4-6)", "varias paginas -> 'págs.'")
check(_m._format_source_line("M.pdf", []) == "- M.pdf", "sem pagina -> so o arquivo")

# --- _parse_pages_by_reference: bloco 'Document Chunks' do only_need_context ---
ctx = (
    "Knowledge Graph Data...\n\n"
    "Document Chunks (Each entry ...):\n\n"
    "```json\n"
    '{"reference_id": "1", "content": "[PÁGINA 64] abc [PÁGINA 65] Expediente"}\n'
    '{"reference_id": "1", "content": "[PÁGINA 39] xyz [PÁGINA 40] [PÁGINA 41]"},\n'
    '{"reference_id": "2", "content": "[PÁGINA 3] outro doc"}\n'
    "```\n"
)
pm = _m._parse_pages_by_reference(ctx)
check(sorted(pm.get("1", [])) == [39, 40, 41, 64, 65], "_parse junta paginas por reference_id (doc 1)")
check(pm.get("2") == [3], "_parse separa por reference_id (doc 2)")
check(_m._parse_pages_by_reference("sem bloco aqui") == {}, "_parse sem bloco -> {}")

# Integracao curta: do contexto ate a linha de fonte formatada
line = _m._format_source_line("M-coordenadores.pdf", pm.get("1", []))
check(line == "- M-coordenadores.pdf (págs. 39-41, 64-65)", f"linha final integrada ({line})")

# --- _parse_cited_pages: paginas que o MODELO citou no texto ---
ans = (
    "Para reembolso, siga os passos.\n> Fonte: [Manual_Viagens.pdf, pág. 12]\n\n"
    "Outro ponto importante.\n> Fonte: [Manual_Coord.pdf, págs. 4-6]\n"
)
cm = _m._parse_cited_pages(ans)
check(cm.get("manual_viagens.pdf") == [12], "_parse_cited_pages: pagina unica")
check(cm.get("manual_coord.pdf") == [4, 5, 6], "_parse_cited_pages: intervalo expandido")
check(_m._parse_cited_pages("sem citacao") == {}, "_parse_cited_pages: sem citacao -> {}")
check(_m._parse_cited_pages("> Fonte: [M.pdf]") == {}, "_parse_cited_pages: sem pagina -> nao entra")
# Modelo escreve com hifen nao-quebravel (‑) e espaco estreito ( ): normaliza
ans_uni = "> Fonte: [M‑coord‑FAI-01.pdf, pág. 70]"
cu = _m._parse_cited_pages(ans_uni)
check(cu.get("m-coord-fai-01.pdf") == [70], f"_parse_cited_pages: normaliza Unicode ({cu})")
check(_m._cited_pages_for("M‑coord‑FAI-01.pdf", cu) == [70], "_cited_pages_for: casa apesar do Unicode")

# --- _cited_pages_for: match frouxo do nome ---
cmap = {"m-coordenadores.pdf": [42]}
check(_m._cited_pages_for("M-Coordenadores.pdf", cmap) == [42], "_cited_pages_for: case-insensitive")
check(_m._cited_pages_for("/docs/M-Coordenadores.pdf", cmap) == [42], "_cited_pages_for: ignora caminho")
check(_m._cited_pages_for("Outro.pdf", cmap) == [], "_cited_pages_for: sem match -> []")

# --- _resolve_pages: o nucleo do hibrido validado ---
check(_m._resolve_pages({10, 11, 12, 40, 41}, [12]) == [12], "hibrido: citada confirmada -> precisa")
check(sorted(_m._resolve_pages({10, 11, 12}, [99])) == [10, 11, 12], "hibrido: citada alucinada -> cai no recuperado")
check(sorted(_m._resolve_pages({10, 11, 12}, [])) == [10, 11, 12], "hibrido: sem citacao -> recuperado")
check(_m._resolve_pages(set(), [12]) == [12], "hibrido: recuperado vazio (falha) -> confia no citado")
check(_m._resolve_pages(set(), []) == [], "hibrido: nada -> sem pagina")
check(sorted(_m._resolve_pages({4, 5, 12}, [12, 99])) == [12], "hibrido: filtra so as citadas validas")

print()
print("RESULTADO:", "TODOS OK" if failures == 0 else f"{failures} FALHA(S)")
sys.exit(1 if failures else 0)
