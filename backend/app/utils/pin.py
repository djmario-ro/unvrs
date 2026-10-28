import secrets
import string


def generate_pin(length: int = 6) -> str:
    """Generate a cryptographically secure numeric PIN."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))



def generate_public_id() -> str:
    """Short URL-safe identifier used in public (guest-facing) room links."""
    return secrets.token_urlsafe(12)
