from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.property import Property, PropertyMembership
from app.models.user import User

router = APIRouter(prefix="/properties", tags=["properties"])


class PropertyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)


@router.get("")
async def properties(user: User = Depends(get_current_user)):
    return user.properties


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate,
    user: User = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_db),
):
    if await db.scalar(select(Property.id).where(Property.slug == body.slug)):
        raise HTTPException(409, "Property slug already exists")
    prop = Property(**body.model_dump())
    db.add(prop)
    await db.flush()
    db.add(PropertyMembership(user_id=user.id, property_id=prop.id, roles=["owner"]))
    return {"id": prop.id, "name": prop.name, "slug": prop.slug, "roles": ["owner"]}
