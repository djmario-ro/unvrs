"""PIN activation and room-scoped, revocable guest device sessions."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.guest_device import GuestDevice
from app.models.guest_room import GuestRoom
from app.models.room import Room
from app.schemas.door import GuestPinRequest, PinValidateRequest
from app.utils import audit as audit_log, ratelimit
from app.utils.homeassistant import DoorUnavailable, open_door

router = APIRouter(prefix="/door", tags=["door"])
COOKIE = "gh_guest"
PIN_REJECTED = "Invalid PIN or outside the booking dates"


def cookie_path(public_id: str) -> str:
    return f"/api/v1/door/{public_id}"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_same_origin(request: Request):
    # JSON + SameSite=Strict prevents form CSRF; checking Origin also covers
    # malicious sibling subdomains. Non-browser clients may omit Origin.
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.frontend_origin.rstrip("/"):
        raise HTTPException(403, "Untrusted origin")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "JSON request required")


def stay_active(stay: GuestRoom, now: datetime) -> bool:
    return not stay.access_revoked_at and (stay.check_in is None or stay.check_in <= now) and (stay.check_out is None or now < stay.check_out)


def session_info(device: GuestDevice, stay: GuestRoom):
    return {"guest": f"{stay.guest.firstname} {stay.guest.lastname}", "room": stay.room.name,
            "expires_at": device.expires_at, "message": "PIN accepted — slide to unlock"}


async def load_device(public_id: str, request: Request, db: AsyncSession):
    token = request.cookies.get(COOKIE, "")
    if len(token) < 32 or len(token) > 128:
        raise HTTPException(401, "Enter your stay PIN to activate this device")
    result = await db.execute(select(GuestDevice).where(GuestDevice.token_hash == token_hash(token)))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(401, "Guest session expired or revoked")
    result = await db.execute(select(GuestRoom).where(GuestRoom.id == device.assignment_id).options(selectinload(GuestRoom.room), selectinload(GuestRoom.guest)))
    stay = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (not stay or device.revoked_at or device.expires_at <= now or not stay_active(stay, now)
            or device.key_version != stay.key_version or device.room_id != stay.room_id
            or stay.room.public_id != public_id):
        raise HTTPException(401, "Guest session expired or revoked")
    return device, stay


@router.post("/validate-pin")
async def validate_pin(body: PinValidateRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Activate this browser only. Entering a PIN never opens hardware."""
    require_same_origin(request)
    now = datetime.now(timezone.utc)
    ip = ratelimit.client_ip(request)
    ratelimit.enforce(f"door:room:{body.room_public_id}", max_attempts=10, window_seconds=60)
    ratelimit.enforce(f"door:ip:{ip}", max_attempts=20, window_seconds=60)
    result = await db.execute(select(GuestRoom).join(Room).where(
        Room.public_id == body.room_public_id, GuestRoom.pin == body.pin,
        GuestRoom.access_revoked_at.is_(None),
        or_(GuestRoom.check_in.is_(None), GuestRoom.check_in <= now),
        or_(GuestRoom.check_out.is_(None), GuestRoom.check_out > now),
    ).options(selectinload(GuestRoom.room), selectinload(GuestRoom.guest)).limit(1))
    stay = result.scalar_one_or_none()
    if not stay:
        room_id = await db.scalar(select(Room.id).where(Room.public_id == body.room_public_id))
        await audit_log.log_detached("door.pin_rejected", f"Invalid, revoked, or out-of-window guest PIN: room id={room_id}")
        raise HTTPException(401, PIN_REJECTED)
    token = secrets.token_urlsafe(32)
    expires = stay.check_out or now + timedelta(days=30)
    device = GuestDevice(assignment_id=stay.id, room_id=stay.room_id, key_version=stay.key_version,
                         token_hash=token_hash(token), device_name=request.headers.get("user-agent", "Guest browser")[:200], expires_at=expires)
    db.add(device)
    await db.flush()
    # Commit before sending a cookie so no cookie can outlive a failed insert.
    await audit_log.log(db, "door.device_activated", f"Device id={device.id} activated for booking id={stay.id}")
    await db.commit()
    response.set_cookie(COOKIE, token, expires=expires, secure=settings.cookie_secure, httponly=True,
                        samesite="strict", path=cookie_path(stay.room.public_id))
    response.headers["Cache-Control"] = "no-store"
    return session_info(device, stay)


@router.post("/{public_id}/session")
async def activate_session(public_id: Annotated[str, Path(min_length=1, max_length=64)],
                           body: GuestPinRequest, request: Request, response: Response,
                           db: AsyncSession = Depends(get_db)):
    # A distinct endpoint makes mixed-version rollouts safe: an old backend
    # returns 404 instead of interpreting PIN activation as a hardware command.
    return await validate_pin(PinValidateRequest(room_public_id=public_id, pin=body.pin), request, response, db)


@router.get("/{public_id}/session")
async def get_session(public_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    device, stay = await load_device(public_id, request, db)
    response.headers["Cache-Control"] = "no-store"
    return session_info(device, stay)


@router.post("/{public_id}/unlock")
async def unlock(public_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    require_same_origin(request)
    device, stay = await load_device(public_id, request, db)
    ratelimit.enforce(f"door:unlock:{device.id}", max_attempts=10, window_seconds=60)
    ratelimit.enforce(f"door:unlock-room:{stay.room_id}", max_attempts=20, window_seconds=60)
    try:
        await open_door(stay.room.homeassistant_entity_id)
    except DoorUnavailable as exc:
        await audit_log.log_detached("door.open_failed", f"Door action not confirmed: room id={stay.room_id}")
        raise HTTPException(503, str(exc)) from exc
    now = datetime.now(timezone.utc)
    if stay.checked_in_at is None:
        stay.checked_in_at = now
        await audit_log.log(db, "door.checkin", f"Guest checked in: guest id={stay.guest_id} room id={stay.room_id}")
    device.last_used_at = now
    await audit_log.log(db, "door.access", f"Door action completed: room id={stay.room_id} device id={device.id}")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Door unlock triggered", "guest": f"{stay.guest.firstname} {stay.guest.lastname}", "room": stay.room.name}


@router.post("/{public_id}/logout", status_code=204)
async def logout(public_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    require_same_origin(request)
    token = request.cookies.get(COOKIE, "")
    if token:
        result = await db.execute(select(GuestDevice).join(GuestRoom, GuestRoom.id == GuestDevice.assignment_id)
                                  .join(Room, Room.id == GuestDevice.room_id)
                                  .where(GuestDevice.token_hash == token_hash(token), Room.public_id == public_id))
        device = result.scalar_one_or_none()
        if device:
            device.revoked_at = datetime.now(timezone.utc)
    response.delete_cookie(COOKIE, path=cookie_path(public_id), secure=settings.cookie_secure, httponly=True, samesite="strict")
