from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Any

class ConversationBase(BaseModel):
    title: str
    rag_engine: str

class ConversationCreate(ConversationBase):
    user_id: str = "guest"

class Conversation(ConversationBase):
    id: int
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class Message(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    metadata: Optional[dict] = {}
    created_at: datetime

    class Config:
        from_attributes = True
