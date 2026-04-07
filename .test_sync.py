from pathlib import Path
from src.chatbot_fai_docs import AppConfig
from src.chatbot_fai_docs.service import RagService

def main():
    config = AppConfig(
        docs_dir=Path("docs/sil"),
        database_url="postgresql://postgres.weicrmqpvrnqngnhecwm:FaiufscarIA2026@aws-1-sa-east-1.pooler.supabase.com:5432/postgres", # Will fail if env not loaded, but from_env works
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dimension=384,
        chunk_size=1200,
        chunk_overlap=200
    )
    # Actually from_env is safer
    config = AppConfig.from_env(docs_dir=Path("docs/sil"))
    service = RagService(config)
    
    print("Testing sync_documents...")
    result = service.sync_documents()
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
