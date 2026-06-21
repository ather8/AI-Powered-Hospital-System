from pydantic import BaseModel


class NoteRequest(BaseModel):
    raw_text: str


class NoteResponse(BaseModel):
    structured_note: str