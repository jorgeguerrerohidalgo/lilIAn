from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def _truncate_password(password: str) -> str:
    """Truncate password to 72 bytes for bcrypt (S1-15 / CVE-2024-32661)."""
    if isinstance(password, str):
        return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return password[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            _truncate_password(plain_password).encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Hashea una contraseña en texto plano con bcrypt.

    Usa bcrypt directamente (``passlib<1.8`` incompat con
    ``bcrypt>=4.2``). Aplica ``_truncate_password`` antes de hashear
    para mitigar CVE-2024-32661.

    Args:
        password: Contraseña en texto plano.

    Returns:
        Hash bcrypt como string utf-8 (compatible con ``verify_password``).
    """
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(_truncate_password(password).encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Genera un JWT firmado con claims estándar.

    Añade automáticamente ``exp``, ``iat``, ``iss`` y ``aud`` a los
    claims provistos en ``data``. Si no se pasa ``expires_delta`` se
    usa ``settings.ACCESS_TOKEN_EXPIRE_MINUTES``.

    Args:
        data: Claims adicionales a incluir en el payload (típicamente
            ``{"sub": user_id, "email": ...}``).
        expires_delta: Delta opcional para controlar la expiración del
            token.

    Returns:
        JWT firmado como string compacto (``header.payload.signature``).
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
    )
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """Decodifica y valida un JWT de acceso.

    Verifica firma, ``aud``, ``iss``, algoritmo y que existan los
    claims ``exp``, ``iat``, ``iss``, ``aud``. Devuelve ``None`` ante
    cualquier ``JWTError``.

    Args:
        token: JWT a decodificar.

    Returns:
        Payload decodificado como ``dict`` o ``None`` si el token es
        inválido, expirado o le falta algún claim obligatorio.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
        return payload
    except JWTError:
        return None
