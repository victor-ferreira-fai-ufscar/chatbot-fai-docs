import hashlib
from pathlib import Path

def get_file_hash(filepath: Path) -> str:
    """Computes the MD5 hash and appends the file size for robust lightweight syncing."""
    if not filepath.exists():
        return ""
    
    file_size = filepath.stat().st_size
    hasher = hashlib.md5()
    
    # Read the file in chunks to handle potentially large PDFs
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
            
    md5_hash = hasher.hexdigest()
    return f"{md5_hash}_{file_size}"

def get_current_date_time_pt_br() -> tuple[str, str]:
    """Retorna a data e hora formatada em PT-BR para o fuso de São Paulo."""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Sao_Paulo")
    except Exception:
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=-3))
        
    now = datetime.now(tz)
    
    weekdays = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    months = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    
    weekday = weekdays[now.weekday()]
    day = now.day
    month = months[now.month - 1]
    year = now.year
    
    date_str = f"{weekday}, {day} de {month} de {year}"
    time_str = now.strftime("%H:%M")
    
    return date_str, time_str
