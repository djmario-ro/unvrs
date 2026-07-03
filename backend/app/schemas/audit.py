from datetime import datetime

from pydantic import BaseModel


class AuditRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    operation: str
    message: str
    created_at: datetime
