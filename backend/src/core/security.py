import bcrypt
from jose import jwt
from src.config import settings


# ── Password ──────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ───────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)  # type: ignore


def decode_token(token: str) -> int | None:
    """Возвращает user_id или None если токен невалидный."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload["sub"])
    except Exception:
        return None