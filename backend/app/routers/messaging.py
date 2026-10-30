from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.message_log import MessageLog
from app.schemas.message import MessageLogRead
from app.utils import messaging

router = APIRouter(prefix="/messaging", tags=["messaging"])


@router.get("/whatsapp/status")
async def whatsapp_status():
    """Report whether the WhatsApp sidecar is linked to a phone number."""
    try:
        return await messaging.whatsapp_status()
    except messaging.MessagingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/whatsapp/qr")
async def whatsapp_qr():
    """Return the current pairing QR to scan, or null once linked."""
    try:
        return await messaging.whatsapp_qr()
    except messaging.MessagingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/logs", response_model=list[MessageLogRead])
async def list_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MessageLog)
        .order_by(MessageLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
