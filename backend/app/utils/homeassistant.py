"""Run the explicitly configured Home Assistant door script after PIN validation."""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DoorUnavailable(Exception):
    """No action was confirmed; the guest must not see a success screen."""


async def open_door(room_public_id: str) -> None:
    script = settings.ha_door_scripts.get(room_public_id)
    if not settings.ha_url.startswith("https://") or not settings.ha_token or not script:
        logger.warning("Door action is not configured for room public_id=%s", room_public_id)
        raise DoorUnavailable("Door control unavailable. Please contact reception.")

    # Calling the script's own service waits for completion (including its
    # three-second relay pulse). Do not retry: a timeout can mean it already ran.
    service = script.removeprefix("script.")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.post(
                f"{settings.ha_url.rstrip('/')}/api/services/script/{service}",
                headers={"Authorization": f"Bearer {settings.ha_token}"},
                json={},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        # Never log tokens, response bodies, or guest PINs.
        code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
        logger.warning("Home Assistant door action failed: %s", code)
        raise DoorUnavailable("Unable to confirm door opening. Please contact reception.") from exc
