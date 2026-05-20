import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

def get_current_date_time_pt_br() -> tuple[str, str]:
    """Retorna a data e hora formatada em PT-BR para o fuso de São Paulo."""
    try:
        tz = ZoneInfo("America/Sao_Paulo")
    except Exception:
        # Fallback caso zoneinfo falhe em alguns ambientes Windows sem tzdata
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

def test():
    print("--- Testando lógica de formatação ---")
    date_str, time_str = get_current_date_time_pt_br()
    print(f"Data formatada: {date_str}")
    print(f"Hora formatada: {time_str}")
    
    # Simular a substituição que o ChatClient faria
    sample_prompt = "Data: {{DATA_ATUAL}} | Hora: {{HORA_ATUAL}}"
    result = sample_prompt.replace("{{DATA_ATUAL}}", date_str).replace("{{HORA_ATUAL}}", time_str)
    print(f"Prompt resultante: {result}")

if __name__ == "__main__":
    test()
