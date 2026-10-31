"""Run the room's explicit Home Assistant lock or script after guest authorization."""
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DoorUnavailable(Exception):
    """No action was confirmed; the guest must not see a success screen."""


async def open_door(entity_id: str | None) -> None:
    if not settings.ha_url.startswith("https://") or not settings.ha_token or not entity_id:
        logger.warning("Door action is not configured")
        raise DoorUnavailable("Door control unavailable. Please contact reception.")

    if not re.fullmatch(r"(lock|script)\.[a-z0-9_]+", entity_id):
        raise DoorUnavailable("Door control unavailable. Please contact reception.")

    # Calling the script's own service waits for completion (including its
    # three-second relay pulse). Do not retry: a timeout can mean it already ran.
    if entity_id.startswith("lock."):
        path, payload = "lock/unlock", {"entity_id": entity_id}
    else:
        path, payload = f"script/{entity_id.removeprefix('script.')}", {}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.post(
                f"{settings.ha_url.rstrip('/')}/api/services/{path}",
                headers={"Authorization": f"Bearer {settings.ha_token}"},
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        # Never log tokens, response bodies, or guest PINs.
        code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
        logger.warning("Home Assistant door action failed: %s", code)
        raise DoorUnavailable("Unable to confirm door opening. Please contact reception.") from exc
