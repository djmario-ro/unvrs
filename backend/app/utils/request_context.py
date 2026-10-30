"""Per-request facts the audit log needs without threading them through every call.

``client_ip`` is set by middleware for every request; ``actor`` is set by
``get_current_user`` once the staff user is resolved. Both are contextvars,
so they are isolated per request even under concurrency.
"""
from contextvars import ContextVar

# (user id, username) of the authenticated staff member, if any.
actor: ContextVar[tuple[int, str] | None] = ContextVar("actor", default=None)
client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
