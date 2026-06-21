from pydantic import BaseModel
from typing import Optional


class PatientInput(BaseModel):
    name: str
    age: int
    symptoms: str
    # Optional session identifier for multi-turn conversations.
    # The client generates a UUID on first load and sends it back with every
    # subsequent message so the server can look up and extend the conversation
    # history. Omit (or send null) for a stateless single-turn exchange.
    session_id: Optional[str] = None
