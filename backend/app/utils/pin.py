import secrets
import string


def generate_pin(length: int = 6) -> str:
    """Generate a cryptographically secure numeric PIN."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(64)
