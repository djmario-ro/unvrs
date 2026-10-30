import base64
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger("app.messaging")

# Status/QR checks are quick; a WhatsApp send can be slow (the first message to
# a recipient sets up an encryption session), so it gets a longer budget.
_TIMEOUT = 10.0
_SEND_TIMEOUT = 30.0


class MessagingError(Exception):
    """Raised when a message could not be handed off to its provider."""


def normalize_phone(raw: str) -> str:
    """Return an E.164 number (with +) for SMS/WhatsApp.

    Handles local Romanian-style input: "0743..." becomes
    "+40743...", "0040..." and "+40..." are kept as international.
    """
    trimmed = raw.strip()
    digits = re.sub(r"\D", "", trimmed)
    if trimmed.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = settings.default_country_code + digits[1:]
    return f"+{digits}"


def _describe(prefix: str, exc: httpx.HTTPError) -> str:
    """Log the full provider error server-side; return a generic, non-leaky
    message that is safe to show in the admin UI and persist in the audit log.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        logger.warning(
            "%s: %s %s -> %s",
            prefix,
            exc.response.status_code,
            exc.request.url,
            exc.response.text[:500],
        )
        return f"{prefix}: gateway returned HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        logger.warning("%s: timed out (%r)", prefix, exc)
        return f"{prefix}: timed out"
    logger.warning("%s: %r", prefix, exc)
    return prefix


# Delivery outcomes recorded in message_logs.status.
SENT = "sent"
MOCKED = "mocked"  # no provider configured: logged locally, nothing delivered


async def send_sms(recipient: str, message: str) -> str:
    """Send an SMS via the sms-gate.app HTTP gateway.

    Returns ``SENT``, or ``MOCKED`` when no gateway is configured — the
    message body is never logged, it contains the door PIN.
    """
    if not settings.sms_gateway_url:
        logger.info("[SMS mock] to=%s chars=%d (no SMS_GATEWAY_URL)", recipient, len(message))
        return MOCKED

    auth = httpx.BasicAuth(settings.sms_gateway_username, settings.sms_gateway_password)
    payload = {"message": message, "phoneNumbers": [recipient]}
    try:
        async with httpx.AsyncClient(timeout=_SEND_TIMEOUT, auth=auth) as client:
            response = await client.post(settings.sms_gateway_url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MessagingError(_describe("SMS gateway error", exc)) from exc
    return SENT


def _whatsapp_headers() -> dict:
    if settings.whatsapp_api_token:
        return {"Authorization": f"Bearer {settings.whatsapp_api_token}"}
    return {}


async def send_whatsapp(
    recipient: str, message: str, image: bytes | None = None
) -> str:
    """Send a WhatsApp message via the Baileys sidecar.

    When ``image`` is given it is sent as a photo with ``message`` as caption.
    Returns ``SENT``, or ``MOCKED`` when no sidecar is configured.
    """
    if not settings.whatsapp_service_url:
        logger.info(
            "[WhatsApp mock] to=%s image=%s chars=%d (no WHATSAPP_SERVICE_URL)",
            recipient,
            bool(image),
            len(message),
        )
        return MOCKED

    payload = {"phone": recipient, "message": message}
    if image is not None:
        payload["image"] = base64.b64encode(image).decode("ascii")
    try:
        async with httpx.AsyncClient(timeout=_SEND_TIMEOUT) as client:
            response = await client.post(
                f"{settings.whatsapp_service_url}/send",
                json=payload,
                headers=_whatsapp_headers(),
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MessagingError(_describe("WhatsApp service error", exc)) from exc
    return SENT


async def whatsapp_status() -> dict:
    """Return the sidecar connection state: {connected, number}."""
    if not settings.whatsapp_service_url:
        return {"connected": False, "number": None}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{settings.whatsapp_service_url}/status",
                headers=_whatsapp_headers(),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise MessagingError(_describe("WhatsApp service error", exc)) from exc


async def whatsapp_qr() -> dict:
    """Return the current pairing QR as {qr}, or {qr: None} once linked."""
    if not settings.whatsapp_service_url:
        return {"qr": None}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{settings.whatsapp_service_url}/qr",
                headers=_whatsapp_headers(),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise MessagingError(_describe("WhatsApp service error", exc)) from exc
