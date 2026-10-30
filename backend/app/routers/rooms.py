import io
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.config import settings
from app.database import get_db
from app.dependencies import require_admin
from app.models.room import Room
from app.models.room_image import RoomImage
from app.schemas.room import RoomCreate, RoomImageRead, RoomRead, RoomUpdate
from app.utils import audit as audit_log
from app.utils.qr import generate_qr_png

router = APIRouter(prefix="/rooms", tags=["rooms"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGES_PER_ROOM = 20
# Real image format (from decode) -> the content type we will store/serve.
_ALLOWED_IMAGE_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}
# private: these are staff-only and should not sit in shared caches.
_IMAGE_CACHE_CONTROL = "private, max-age=31536000, immutable"


async def _load_room(db: AsyncSession, room_id: int) -> Room:
    result = await db.execute(
        select(Room).where(Room.id == room_id).options(selectinload(Room.images))
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.get("", response_model=list[RoomRead])
async def list_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Room).options(selectinload(Room.images)).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=RoomRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_room(body: RoomCreate, db: AsyncSession = Depends(get_db)):
    room = Room(**body.model_dump())
    db.add(room)
    await db.flush()
    await audit_log.log(db, "room.create", f"Created room '{room.name}' (id={room.id})")
    return await _load_room(db, room.id)


@router.get("/{room_id}", response_model=RoomRead)
async def get_room(room_id: int, db: AsyncSession = Depends(get_db)):
    return await _load_room(db, room_id)


@router.patch(
    "/{room_id}", response_model=RoomRead, dependencies=[Depends(require_admin)]
)
async def update_room(
    room_id: int, body: RoomUpdate, db: AsyncSession = Depends(get_db)
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(room, field, value)
    await audit_log.log(db, "room.update", f"Updated room id={room_id}")
    await db.flush()
    return await _load_room(db, room_id)


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_room(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    await audit_log.log(db, "room.delete", f"Deleted room '{room.name}' (id={room_id})")
    await db.delete(room)


@router.post(
    "/{room_id}/images",
    response_model=RoomImageRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def upload_room_image(
    room_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large (max 5 MB)",
        )
    # Validate it is actually an image and derive the type from the real format
    # rather than trusting the client-supplied content-type.
    try:
        probe = Image.open(io.BytesIO(content))
        image_format = probe.format
        probe.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="File is not a valid image")
    content_type = _ALLOWED_IMAGE_TYPES.get(image_format or "")
    if not content_type:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    count = await db.scalar(
        select(func.count()).select_from(RoomImage).where(RoomImage.room_id == room_id)
    )
    if count >= MAX_IMAGES_PER_ROOM:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_IMAGES_PER_ROOM} images per room",
        )

    image = RoomImage(
        room_id=room_id,
        filename=file.filename or "image",
        content_type=content_type,
        content=content,
        is_cover=count == 0,  # first photo becomes the cover
    )
    db.add(image)
    await db.flush()
    await audit_log.log(
        db, "room.image_added", f"Added image id={image.id} to room id={room_id}"
    )
    await db.refresh(image)
    return image


def _thumbnail(data: bytes, width: int) -> bytes:
    """Downscale to ``width`` px wide, preserving aspect and format."""
    img = Image.open(io.BytesIO(data))
    fmt = img.format or "PNG"
    if img.width <= width:
        return data  # never upscale
    height = round(img.height * width / img.width)
    img = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    save_kwargs = {"quality": 82} if fmt in {"JPEG", "WEBP"} else {}
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


@router.get("/{room_id}/images/{image_id}")
async def get_room_image(
    room_id: int,
    image_id: int,
    request: Request,
    w: int | None = Query(None, ge=16, le=2048, description="Downscale to this width"),
    db: AsyncSession = Depends(get_db),
):
    # Image bytes are immutable per (id, width), so they cache forever with a
    # strong ETag that includes the requested width.
    etag = f'"img-{image_id}-w{w or 0}"'
    headers = {"ETag": etag, "Cache-Control": _IMAGE_CACHE_CONTROL}
    if request.headers.get("if-none-match") == etag:
        # Cached copy still valid — return 304 without loading the blob.
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    result = await db.execute(
        select(RoomImage)
        .where(RoomImage.id == image_id, RoomImage.room_id == room_id)
        .options(undefer(RoomImage.content))
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    content = _thumbnail(image.content, w) if w else image.content
    return Response(
        content=content, media_type=image.content_type, headers=headers
    )


@router.delete(
    "/{room_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_room_image(
    room_id: int, image_id: int, db: AsyncSession = Depends(get_db)
):
    image = await db.get(RoomImage, image_id)
    if not image or image.room_id != room_id:
        raise HTTPException(status_code=404, detail="Image not found")
    await audit_log.log(
        db, "room.image_deleted", f"Deleted image id={image_id} from room id={room_id}"
    )
    await db.delete(image)


@router.post(
    "/{room_id}/images/{image_id}/cover",
    response_model=RoomImageRead,
    dependencies=[Depends(require_admin)],
)
async def set_cover_image(
    room_id: int, image_id: int, db: AsyncSession = Depends(get_db)
):
    """Mark one image as the room's cover and unset the others."""
    target = await db.get(RoomImage, image_id)
    if not target or target.room_id != room_id:
        raise HTTPException(status_code=404, detail="Image not found")
    result = await db.execute(select(RoomImage).where(RoomImage.room_id == room_id))
    for image in result.scalars().all():
        image.is_cover = image.id == image_id
    await db.flush()
    await db.refresh(target)
    return target


@router.post("/{room_id}/cleaned", status_code=status.HTTP_204_NO_CONTENT)
async def mark_room_cleaned(room_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a room cleaned, clearing the 'checked out' housekeeping state."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    room.cleaned_at = datetime.now(tz=timezone.utc)
    await audit_log.log(db, "room.cleaned", f"Room id={room_id} marked cleaned")


@router.get("/{room_id}/qr", summary="Get QR code PNG for door access")
async def get_room_qr(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    door_url = f"{settings.frontend_origin}/door/{room.public_id}"
    png_bytes = generate_qr_png(door_url)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )
