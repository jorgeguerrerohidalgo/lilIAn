"""Pydantic v2 schemas for auth self-service endpoints (Phase 1b).

Schemas kept separate from ``user.py`` because these endpoints
(``PATCH /auth/me``, ``POST /auth/change-password``,
``POST /auth/forgot-password``, ``POST /auth/reset-password``) belong to
the auth router and have their own validation rules — they don't belong
on the public User CRUD surface.

Each schema is intentionally minimal: the strongest input validation
the password policy allows (``_validate_password_strength``) is
re-exported so we cannot drift between ``UserCreate.password`` rules and
the password the user types when resetting.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import _validate_password_strength

_FULL_NAME_MAX_LEN = 255
_PHONE_MAX_LEN = 50


class UserUpdate(BaseModel):
    """Phase 1b — body of ``PATCH /auth/me``.

    Only the fields the user can self-edit without re-verification.
    Email changes require re-verification, so they are explicitly
    excluded from this schema and belong in a separate endpoint (out
    of scope for Phase 1b).
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=_FULL_NAME_MAX_LEN)
    phone: str | None = Field(default=None, max_length=_PHONE_MAX_LEN)


class ChangePasswordRequest(BaseModel):
    """Phase 1b — body of ``POST /auth/change-password``.

    Both fields are required: the endpoint must verify the current
    password before accepting a new one. The ``new_password`` validator
    is the same rule used by ``UserCreate.password`` so the policy
    stays consistent across signup and self-service change.
    """

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class ForgotPasswordRequest(BaseModel):
    """Phase 1b — body of ``POST /auth/forgot-password``.

    The endpoint always responds ``202 Accepted`` regardless of whether
    the email is registered — we use ``EmailStr`` to reject obviously
    malformed input but never to leak which addresses exist.
    """

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Phase 1b — body of ``POST /auth/reset-password``.

    The token comes from the email link the user clicked. It is opaque
    and short-lived (1 h); see ``app.api.endpoints.auth``.
    """

    token: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_strength(cls, value: str) -> str:
        return _validate_password_strength(value)
