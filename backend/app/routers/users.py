from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.utils import audit as audit_log
from app.utils.auth import hash_password

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(require_admin)]
)


@router.get("", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await audit_log.log(
        db, "user.create", f"Created user {user.username} ({user.role})"
    )
    await db.refresh(user)
    return user


def _is_master(user: User) -> bool:
    """The env-managed admin: created and reset from ADMIN_* on every boot."""
    return user.username == settings.admin_username


async def _admin_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).where(User.role == "admin"))
    return result.scalar_one()


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    body: UserUpdate,
    current: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if _is_master(user):
        raise HTTPException(
            status_code=400,
            detail="This account is managed by ADMIN_USERNAME/ADMIN_PASSWORD on the server",
        )
    if body.role and body.role != user.role:
        if user.id == current.id:
            raise HTTPException(status_code=400, detail="You cannot change your own role")
        if user.role == "admin" and await _admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last admin")
    if body.password:
        user.password_hash = hash_password(body.password)
        user.token_version += 1  # invalidate that user's existing sessions
    if body.role:
        user.role = body.role
    await audit_log.log(db, "user.update", f"Updated user id={user_id}")
    await db.flush()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if _is_master(user):
        raise HTTPException(
            status_code=400,
            detail="This account is managed by ADMIN_USERNAME/ADMIN_PASSWORD on the server",
        )
    if user.role == "admin" and await _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    await audit_log.log(db, "user.delete", f"Deleted user {user.username} (id={user_id})")
    await db.delete(user)
