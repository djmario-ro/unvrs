from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.audit import Audit
from app.utils import request_context


def _entry(operation: str, message: str) -> Audit:
    who = request_context.actor.get()
    return Audit(
        operation=operation,
        message=message,
        actor_id=who[0] if who else None,
        actor=who[1] if who else None,
        ip=request_context.client_ip.get(),
    )


async def log(session: AsyncSession, operation: str, message: str) -> None:
    """Record an operation in the caller's transaction.

    Commits (or rolls back) together with the change it describes, so a
    failed request leaves no audit row.
    """
    session.add(_entry(operation, message))


async def log_detached(operation: str, message: str) -> None:
    """Record an event that must survive the request failing.

    Used for security events on error paths (failed login, rejected PIN):
    the request's own session is rolled back when the 4xx is raised, so
    this writes and commits in a session of its own.
    """
    async with AsyncSessionLocal() as session:
        session.add(_entry(operation, message))
        await session.commit()
