import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


_PASSWORD_MIN_LEN = 12


def _validate_password_strength(value: str) -> str:
    """S1-04: enforce a minimum-strength policy on user passwords.

    Rules (kept deliberately simple — a server-side strength meter can be
    added later without breaking clients):
      - minimum 12 characters
      - at least one lowercase letter
      - at least one uppercase letter
      - at least one digit
      - at least one symbol (any non-alphanumeric)
    """
    if len(value) < _PASSWORD_MIN_LEN:
        raise ValueError(
            f"La contraseña debe tener al menos {_PASSWORD_MIN_LEN} caracteres"
        )
    if not re.search(r"[a-z]", value):
        raise ValueError("La contraseña debe incluir al menos una letra minúscula")
    if not re.search(r"[A-Z]", value):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula")
    if not re.search(r"\d", value):
        raise ValueError("La contraseña debe incluir al menos un dígito")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("La contraseña debe incluir al menos un símbolo")
    return value


class UserCreate(UserBase):
    password: str = Field(min_length=_PASSWORD_MIN_LEN, max_length=128)

    @field_validator("password")
    @classmethod
    def _check_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    phone: str | None = None
    status: str
    created_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class UserInDB(UserBase):
    id: int
    password_hash: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
