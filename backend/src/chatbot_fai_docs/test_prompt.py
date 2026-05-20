import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from chatbot_fai_docs.llm import get_current_date_time_pt_br, ChatClient

def test():
    print("--- Testando formatação de data/hora ---")
    date_str, time_str = get_current_date_time_pt_br()
    print(f"Data formatada: {date_str}")
    print(f"Hora formatada: {time_str}")
    
    print("\n--- Testando substituição no Prompt ---")
    client = ChatClient()
    # Mocking answer parameters to see what system_prompt would look like
    # We'll just check if the placeholders are gone in the base
    prompt = client.system_prompt_base.replace("{{DATA_ATUAL}}", date_str).replace("{{HORA_ATUAL}}", time_str)
    
    if "{{DATA_ATUAL}}" in prompt or "{{HORA_ATUAL}}" in prompt:
        print("ERRO: Placeholders ainda presentes!")
    else:
        print("SUCESSO: Placeholders substituídos corretamente.")
        # Print a snippet to verify
        start_idx = prompt.find("Data Atual:")
        if start_idx != -1:
            print(f"Resultado: {prompt[start_idx:start_idx+100]}...")

if __name__ == "__main__":
    test()
