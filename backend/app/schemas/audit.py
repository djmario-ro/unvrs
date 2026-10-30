from datetime import datetime

from pydantic import BaseModel


class AuditRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    operation: str
    message: str
    actor: str | None  # staff username; None for door/system events
    ip: str | None
    created_at: datetime
