"""Testes da limpeza do bucket temporario (funcoes puras, sem rede).

    python3 backend/src/chatbot_fai_docs/test_temp_cleanup.py

select_expired e _parse_dt nao tocam a rede; cleanup_once e exercitada com um
StorageService FALSO (list/delete em memoria), entao roda no host sem Supabase.
"""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

_mod_path = Path(__file__).resolve().parent / "temp_cleanup.py"
_spec = importlib.util.spec_from_file_location("_temp_cleanup_ut", _mod_path)
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)

failures = 0


def check(cond, msg):
    global failures
    if not cond:
        failures += 1
    print(f"[{'ok ' if cond else 'FALHOU'}] {msg}")


NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def obj(name, created):
    return {"name": name, "created_at": created}


# --- _parse_dt: ISO do Supabase, com Z, e tz-aware ---
check(tc._parse_dt("2026-06-10T13:35:31.492Z") == datetime(2026, 6, 10, 13, 35, 31, 492000, tzinfo=timezone.utc),
      "_parse_dt converte ISO com Z para UTC")
check(tc._parse_dt(None) is None, "_parse_dt None -> None")
check(tc._parse_dt("data-ruim") is None, "_parse_dt invalido -> None")

# --- select_expired: > 3 dias sai; <= 3 dias e sem data ficam ---
objs = [
    obj("velho.xlsx", "2026-06-10T12:00:00Z"),     # 8 dias -> expira
    obj("limite.pdf", "2026-06-15T12:00:00.000Z"),  # exatamente 3 dias -> NAO expira (cutoff estrito)
    obj("quase.pdf", "2026-06-15T11:59:59Z"),       # 3 dias + 1s -> expira
    obj("novo.csv", "2026-06-18T09:00:00Z"),        # hoje -> fica
    {"name": "sem_data", "created_at": None},        # sem data -> nunca deleta
    {"created_at": "2026-01-01T00:00:00Z"},          # sem nome -> ignora
]
expired = tc.select_expired(objs, NOW, max_age_days=3)
check(expired == ["velho.xlsx", "quase.pdf"], f"select_expired pega so os vencidos ({expired})")
check("limite.pdf" not in expired, "select_expired: exatamente 3 dias NAO expira")
check("sem_data" not in expired, "select_expired: objeto sem data nunca e deletado")

# --- cleanup_once: integra list -> select -> delete com storage fake ---
class FakeStorage:
    def __init__(self, objs):
        self._objs = list(objs)
        self.deleted = []
        self.bucket = "gerados"
    def list_objects(self, limit=1000):
        return self._objs
    def delete(self, name):
        if name == "boom.pdf":
            raise RuntimeError("falha simulada")
        self.deleted.append(name)

fs = FakeStorage([
    obj("velho.xlsx", "2026-06-01T00:00:00Z"),
    obj("novo.csv", "2026-06-18T00:00:00Z"),
    obj("boom.pdf", "2026-06-01T00:00:00Z"),  # vencido mas delete falha
])
summary = tc.cleanup_once(fs, max_age_days=3, now=NOW)
check(summary["scanned"] == 3, "cleanup_once: scanned conta todos")
check(fs.deleted == ["velho.xlsx"], "cleanup_once: deleta so o vencido que da certo")
check(summary["deleted"] == ["velho.xlsx"], "cleanup_once: resumo lista os deletados")
check(len(summary["errors"]) == 1 and summary["errors"][0][0] == "boom.pdf",
      "cleanup_once: erro por objeto nao interrompe e e registrado")
check("novo.csv" not in fs.deleted, "cleanup_once: nao toca em arquivo novo")

print()
print("RESULTADO:", "TODOS OK" if failures == 0 else f"{failures} FALHA(S)")
sys.exit(1 if failures else 0)
