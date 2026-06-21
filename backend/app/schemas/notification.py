from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class NotificationCreate(BaseModel):
    user_id: int
    message: str
    scheduled_for: datetime | None = None


class NotificationResponse(BaseModel):
    id: UUID
    user_id: int
    message: str
    read: bool
    created_at: datetime
    scheduled_for: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    """Minimal user info for populating the admin "send notification"
    recipient picker — deliberately excludes hashed_password and other
    fields that route has no business returning."""
    id: int
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)
