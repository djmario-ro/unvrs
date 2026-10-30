from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.guest import Guest
from app.schemas.guest import GuestCreate, GuestRead, GuestUpdate
from app.utils import audit as audit_log

router = APIRouter(prefix="/guests", tags=["guests"])


@router.get("", response_model=list[GuestRead])
async def list_guests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Guest).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("", response_model=GuestRead, status_code=status.HTTP_201_CREATED)
async def create_guest(body: GuestCreate, db: AsyncSession = Depends(get_db)):
    guest = Guest(**body.model_dump())
    db.add(guest)
    await db.flush()
    await audit_log.log(
        db, "guest.create", f"Created guest {guest.firstname} {guest.lastname} (id={guest.id})"
    )
    await db.refresh(guest)
    return guest


@router.get("/{guest_id}", response_model=GuestRead)
async def get_guest(guest_id: int, db: AsyncSession = Depends(get_db)):
    guest = await db.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest


@router.patch("/{guest_id}", response_model=GuestRead)
async def update_guest(
    guest_id: int, body: GuestUpdate, db: AsyncSession = Depends(get_db)
):
    guest = await db.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(guest, field, value)
    await audit_log.log(db, "guest.update", f"Updated guest id={guest_id}")
    await db.flush()
    await db.refresh(guest)
    return guest


@router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guest(guest_id: int, db: AsyncSession = Depends(get_db)):
    guest = await db.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    # Id only: the name would outlive the guest record in an admin-visible table.
    await audit_log.log(db, "guest.delete", f"Deleted guest id={guest_id}")
    await db.delete(guest)
