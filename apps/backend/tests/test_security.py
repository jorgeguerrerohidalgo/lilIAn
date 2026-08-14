"""Tests for app.core.security — password hashing and JWT helpers.

Covers S6-19:
- bcrypt hash/verify round-trip
- create_access_token includes ``sub``, ``exp``, ``iat``, ``iss``, ``aud``
- decode_access_token round-trips
- expired, bad-signature, wrong-issuer, wrong-audience tokens all
  decode to ``None``

Tests are pure-Python (no DB) — the module is dependency-free.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


# ===========================================================================
# Password hashing
# ===========================================================================
class TestPasswordHash:
    def test_hash_password_returns_bcrypt_format(self):
        hashed = get_password_hash("Test1234!Abcd")
        assert isinstance(hashed, str)
        # bcrypt hash starts with $2b$ (or $2a$ / $2y$)
        assert hashed.startswith(("$2a$", "$2b$", "$2y$"))

    def test_hash_password_is_unique_per_call(self):
        """bcrypt salt is random — two hashes of the same password differ."""
        a = get_password_hash("SamePass1!")
        b = get_password_hash("SamePass1!")
        assert a != b

    def test_verify_password_valid(self):
        hashed = get_password_hash("Test1234!Abcd")
        assert verify_password("Test1234!Abcd", hashed) is True

    def test_verify_password_wrong(self):
        hashed = get_password_hash("Test1234!Abcd")
        assert verify_password("WrongPass1!", hashed) is False

    def test_verify_password_returns_false_on_garbage_hash(self):
        """Defensive: malformed hash must NOT raise, must return False."""
        assert verify_password("anything", "not-a-bcrypt-hash") is False

    def test_hash_truncates_long_passwords(self):
        """S1-15 / CVE-2024-32661: passwords >72 bytes are truncated,
        so a long password should still verify when the first 72 bytes
        match the original (i.e. both get truncated to the same value).
        """
        long_pw = "A" * 200 + "1!xy"  # > 72 bytes
        hashed = get_password_hash(long_pw)
        # Different tail, same first 72 bytes
        different_tail = "A" * 200 + "9!zz"
        assert verify_password(different_tail, hashed) is True


# ===========================================================================
# JWT access tokens — positive
# ===========================================================================
class TestCreateAccessToken:
    def test_create_access_token_contains_required_claims(self):
        token = create_access_token(data={"sub": "42", "email": "u@e.com"})
        # Decode WITHOUT verification to inspect claims
        from jose import jwt

        payload = jwt.get_unverified_claims(token)

        assert payload["sub"] == "42"
        assert payload["email"] == "u@e.com"
        # Standard claims injected by create_access_token
        assert "exp" in payload
        assert "iat" in payload
        assert payload["iss"] == settings.JWT_ISSUER
        assert payload["aud"] == settings.JWT_AUDIENCE

    def test_create_access_token_default_expiry(self):
        from jose import jwt

        token = create_access_token(data={"sub": "1"})
        payload = jwt.get_unverified_claims(token)
        exp = datetime.fromtimestamp(payload["exp"], UTC)
        iat = datetime.fromtimestamp(payload["iat"], UTC)
        delta = exp - iat
        # Should be settings.ACCESS_TOKEN_EXPIRE_MINUTES minutes
        expected_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert abs(delta.total_seconds() - expected_seconds) < 5

    def test_create_access_token_custom_expiry(self):
        from jose import jwt

        token = create_access_token(
            data={"sub": "1"},
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.get_unverified_claims(token)
        delta = datetime.fromtimestamp(payload["exp"], UTC) - datetime.fromtimestamp(
            payload["iat"], UTC
        )
        assert abs(delta.total_seconds() - 300) < 5


class TestDecodeTokenValid:
    def test_decode_token_round_trip(self):
        token = create_access_token(data={"sub": "123", "email": "a@b.com"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["email"] == "a@b.com"
        assert payload["iss"] == settings.JWT_ISSUER
        assert payload["aud"] == settings.JWT_AUDIENCE

    def test_decode_token_without_data(self):
        token = create_access_token(data={"sub": "1"})
        assert decode_access_token(token) is not None


# ===========================================================================
# JWT access tokens — negative
# ===========================================================================
class TestDecodeTokenFailures:
    def test_decode_token_expired(self):
        """An expired token must decode to None (not raise)."""
        token = create_access_token(
            data={"sub": "1"},
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        # iat must be in the past relative to exp — both are in the past
        assert decode_access_token(token) is None

    def test_decode_token_invalid_signature(self):
        """A token signed with a different secret must be rejected."""
        from jose import jwt

        bad = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC),
                "iss": settings.JWT_ISSUER,
                "aud": settings.JWT_AUDIENCE,
            },
            "a-completely-different-secret-32-bytes-long-xxx",
            algorithm=settings.JWT_ALGORITHM,
        )
        assert decode_access_token(bad) is None

    def test_decode_token_wrong_issuer(self):
        from jose import jwt

        bad = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC),
                "iss": "evil-issuer",
                "aud": settings.JWT_AUDIENCE,
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        assert decode_access_token(bad) is None

    def test_decode_token_wrong_audience(self):
        from jose import jwt

        bad = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC),
                "iss": settings.JWT_ISSUER,
                "aud": "evil-audience",
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        assert decode_access_token(bad) is None

    def test_decode_token_garbage(self):
        assert decode_access_token("not.a.jwt") is None
        assert decode_access_token("") is None
        assert decode_access_token("only.two.parts.bad") is None

    def test_decode_token_missing_required_claims(self):
        """Tokens missing exp/iat/iss/aud must be rejected (require option)."""
        from jose import jwt

        bad = jwt.encode(
            {"sub": "1"},  # only sub — no exp/iat/iss/aud
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        assert decode_access_token(bad) is None