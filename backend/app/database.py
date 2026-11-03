from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# All authenticated ORM reads (including db.get and relationship loads) share
# this boundary. Public door requests use their room-scoped device capability
# instead; they never receive an authenticated tenant session.
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria


@event.listens_for(Session, "do_orm_execute")
def scope_property_reads(execute_state):
    from app.models.property import PropertyScoped

    property_id = execute_state.session.info.get("property_id")
    if property_id is not None and execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                PropertyScoped,
                lambda cls: cls.property_id == property_id,
                include_aliases=True,
            )
        )


@event.listens_for(Session, "before_flush")
def scope_property_writes(session, flush_context, instances):
    from app.models.property import PropertyScoped

    property_id = session.info.get("property_id")
    if property_id is None:
        return
    for obj in session.new | session.dirty | session.deleted:
        if isinstance(obj, PropertyScoped):
            if obj.property_id is None and obj in session.new:
                obj.property_id = property_id
            elif obj.property_id != property_id:
                raise ValueError("Cross-property write refused")
