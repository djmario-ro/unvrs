from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Audit


async def log(session: AsyncSession, operation: str, message: str) -> None:
    entry = Audit(operation=operation, message=message)
    session.add(entry)
