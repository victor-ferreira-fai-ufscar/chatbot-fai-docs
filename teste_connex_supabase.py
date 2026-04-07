import os
import sys
from dotenv import load_dotenv

# Appends project path so Python can find src
sys.path.append(r"c:\Users\joao.silva\OneDrive - FAIUFSCar\Área de Trabalho\FAI - DESENVOLVIMENTO\chatbot-fai-docs")

# Load from .env
load_dotenv(r"c:\Users\joao.silva\OneDrive - FAIUFSCar\Área de Trabalho\FAI - DESENVOLVIMENTO\chatbot-fai-docs\.env")
db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("ERRO: DATABASE_URL nao foi encontrada no .env!")
    sys.exit(1)

from src.chatbot_fai_docs.vector_store import build_vector_store

print(f"DATABASE_URL encontrada: {db_url[:15]}...{db_url[-5:]}")
print("Tentando conexao com o Supabase usando pgvector...")

try:
    v_store = build_vector_store(database_url=db_url, embedding_dimension=384)
    v_store.ensure_ready()
    count = v_store.count()
    print("CONEXAO BEM SUCEDIDA!")
    print(f"Total de chunks atualmente na tabela document_chunks no Supabase: {count}")
except Exception as e:
    print(f"FALHA NA CONEXAO: {e}")
    sys.exit(1)
