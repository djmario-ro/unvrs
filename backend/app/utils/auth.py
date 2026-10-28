from datetime import datetime, timedelta, timezone

import bcrypt
import jwt  # PyJWT

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt only considers the first 72 bytes of the password.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    pw = password.encode("utf-8")[:72]
    return bcrypt.checkpw(pw, password_hash.encode("utf-8"))


def create_access_token(user_id: int, token_version: int) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(
        hours=settings.access_token_expire_hours
    )
    payload = {"sub": str(user_id), "tv": token_version, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
