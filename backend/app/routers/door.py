from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.guest_room import GuestRoom
from app.models.token import Token
from app.schemas.token import PinValidateRequest
from app.utils import audit as audit_log
from app.utils.pin import generate_token

router = APIRouter(prefix="/door", tags=["door"])

COOKIE_NAME = "guesthouse_session"


@router.post("/validate-pin")
async def validate_pin(
    body: PinValidateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a guest PIN for a given room.
    On success, issue an httponly session cookie.
    """
    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(GuestRoom)
        .where(GuestRoom.room_id == body.room_id, GuestRoom.pin == body.pin)
        .options(selectinload(GuestRoom.room), selectinload(GuestRoom.guest))
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN"
        )

    # Check check-out hasn't passed
    if assignment.check_out and assignment.check_out < now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your stay has ended",
        )

    # Create session token
    raw_token = generate_token()
    valid_until = now + timedelta(hours=settings.access_token_expire_hours)
    token = Token(
        assignment_id=assignment.id,
        token=raw_token,
        valid_until=valid_until,
    )
    db.add(token)

    await audit_log.log(
        db,
        "door.access",
        f"Door access granted: guest id={assignment.guest_id} room id={body.room_id}",
    )

    await db.flush()

    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_hours * 3600,
        path="/",
    )

    return {
        "message": "Access granted",
        "guest": f"{assignment.guest.firstname} {assignment.guest.lastname}",
        "room": assignment.room.name,
        "valid_until": valid_until.isoformat(),
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"message": "Logged out"}
