from __future__ import annotations
import json
import psycopg
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class ConversationRecord:
    id: int
    user_id: str
    title: str
    rag_engine: str
    created_at: datetime

@dataclass
class MessageRecord:
    id: int
    conversation_id: int
    role: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime

class PostgresChatRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def ensure_ready(self) -> None:
        """Cria as tabelas de conversas e mensagens se nao existirem."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Tabela de Conversas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_conversations (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        rag_engine TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                # Tabela de Mensagens
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER REFERENCES chat_conversations(id) ON DELETE CASCADE,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            conn.commit()

    def create_conversation(self, title: str, rag_engine: str, user_id: str = "guest") -> int:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_conversations (user_id, title, rag_engine) VALUES (%s, %s, %s) RETURNING id",
                    (user_id, title, rag_engine)
                )
                conv_id = cur.fetchone()[0]
            conn.commit()
        return conv_id

    def list_conversations(self, user_id: str = "guest") -> list[ConversationRecord]:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, user_id, title, rag_engine, created_at FROM chat_conversations WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                rows = cur.fetchall()
                return [
                    ConversationRecord(
                        id=row[0],
                        user_id=row[1],
                        title=row[2],
                        rag_engine=row[3],
                        created_at=row[4]
                    )
                    for row in rows
                ]

    def get_messages(self, conversation_id: int) -> list[MessageRecord]:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, conversation_id, role, content, metadata, created_at FROM chat_messages WHERE conversation_id = %s ORDER BY id ASC",
                    (conversation_id,)
                )
                rows = cur.fetchall()
                return [
                    MessageRecord(
                        id=row[0],
                        conversation_id=row[1],
                        role=row[2],
                        content=row[3],
                        metadata=row[4] if row[4] else {},
                        created_at=row[5]
                    )
                    for row in rows
                ]

    def add_message(self, conversation_id: int, role: str, content: str, metadata: Optional[dict] = None) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_messages (conversation_id, role, content, metadata) VALUES (%s, %s, %s, %s)",
                    (conversation_id, role, content, json.dumps(metadata) if metadata else None)
                )
            conn.commit()

    def update_title(self, conversation_id: int, new_title: str) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_conversations SET title = %s WHERE id = %s",
                    (new_title, conversation_id)
                )
            conn.commit()

    def delete_conversation(self, conversation_id: int) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chat_conversations WHERE id = %s", (conversation_id,))
            conn.commit()


class InMemoryChatRepository:
    """Simple in-memory repository used when no external Postgres is configured.
    Not persistent across restarts; intended for local development with LightRAG.
    """
    def __init__(self) -> None:
        self._conversations: list[ConversationRecord] = []
        self._messages: dict[int, list[MessageRecord]] = {}
        self._next_conv_id = 1
        self._next_msg_id = 1

    def ensure_ready(self) -> None:
        return

    def create_conversation(self, title: str, rag_engine: str, user_id: str = "guest") -> int:
        conv = ConversationRecord(id=self._next_conv_id, user_id=user_id, title=title, rag_engine=rag_engine, created_at=datetime.utcnow())
        self._conversations.insert(0, conv)
        self._messages[conv.id] = []
        self._next_conv_id += 1
        return conv.id

    def list_conversations(self, user_id: str = "guest") -> list[ConversationRecord]:
        return [c for c in self._conversations if c.user_id == user_id]

    def get_messages(self, conversation_id: int) -> list[MessageRecord]:
        return self._messages.get(conversation_id, [])

    def add_message(self, conversation_id: int, role: str, content: str, metadata: Optional[dict] = None) -> None:
        msg = MessageRecord(id=self._next_msg_id, conversation_id=conversation_id, role=role, content=content, metadata=metadata or {}, created_at=datetime.utcnow())
        self._messages.setdefault(conversation_id, []).append(msg)
        self._next_msg_id += 1

    def update_title(self, conversation_id: int, new_title: str) -> None:
        for c in self._conversations:
            if c.id == conversation_id:
                c.title = new_title
                return

    def delete_conversation(self, conversation_id: int) -> None:
        self._conversations = [c for c in self._conversations if c.id != conversation_id]
        if conversation_id in self._messages:
            del self._messages[conversation_id]


def get_repo_from_url(database_url: Optional[str]):
    """Factory: return a Postgres repo if database_url provided, otherwise in-memory repo."""
    if database_url:
        return PostgresChatRepository(database_url)
    return InMemoryChatRepository()
