"""Limpeza do bucket de documentos TEMPORARIOS (gerados pelo agente).

O Supabase Storage self-hosted nao tem TTL/lifecycle nativo, entao varremos o
bucket periodicamente e removemos os objetos com `created_at` mais antigo que o
limite (TEMP_DOC_TTL_DAYS). `select_expired` e PURA (sem rede) para teste isolado;
`cleanup_once` orquestra list -> select -> delete usando um StorageService ja
apontado para o bucket temporario.

SEGURANCA: nunca chame isto com um StorageService do bucket de manuais — ele
deleta tudo que estiver vencido no bucket configurado.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _parse_dt(value) -> "datetime | None":
    """Converte o timestamp ISO 8601 do Supabase (ex.: '2026-06-10T13:35:31.492Z')
    para datetime tz-aware (UTC). Retorna None se ausente/invalido."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Normaliza para tz-aware (assume UTC se vier sem tz)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def select_expired(objects: list, now: datetime, max_age_days: int) -> list:
    """Nomes dos objetos cujo `created_at` e mais antigo que (now - max_age_days).

    Objetos sem data parseavel sao IGNORADOS (nunca deletados por precaucao) —
    cobre entradas-pasta/placeholder que o list as vezes retorna sem metadados.
    """
    cutoff = now - timedelta(days=max_age_days)
    expired = []
    for obj in objects or []:
        name = (obj or {}).get("name")
        if not name:
            continue
        created = _parse_dt(obj.get("created_at") or obj.get("updated_at"))
        if created is None:
            continue
        if created < cutoff:
            expired.append(name)
    return expired


def cleanup_once(storage, max_age_days: int, now: "datetime | None" = None) -> dict:
    """Lista o bucket do `storage`, deleta os objetos vencidos e devolve um resumo
    {scanned, deleted: [...], errors: [(nome, msg), ...]}. Erros por objeto nao
    interrompem a varredura."""
    now = now or datetime.now(timezone.utc)
    objects = storage.list_objects(limit=1000)
    expired = select_expired(objects, now, max_age_days)
    deleted, errors = [], []
    for name in expired:
        try:
            storage.delete(name)
            deleted.append(name)
        except Exception as e:  # noqa: BLE001 - registra e segue
            errors.append((name, str(e)))
    return {"scanned": len(objects), "deleted": deleted, "errors": errors}
