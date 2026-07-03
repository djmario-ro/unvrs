from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import Audit
from app.schemas.audit import AuditRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditRead])
async def list_audit(
    skip: int = 0, limit: int = 200, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Audit).order_by(Audit.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()
