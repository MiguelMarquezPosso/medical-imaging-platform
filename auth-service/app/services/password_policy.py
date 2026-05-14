"""Password policy enforcement."""

from __future__ import annotations

import string

from app.core.config import get_settings
from app.core.errors import ValidationError


def enforce_password_policy(password: str) -> None:
    s = get_settings()
    if len(password) < s.PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"Password must be at least {s.PASSWORD_MIN_LENGTH} characters long"
        )
    if s.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        raise ValidationError("Password must contain an uppercase letter")
    if s.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain a digit")
    if s.PASSWORD_REQUIRE_SYMBOL and not any(c in string.punctuation for c in password):
        raise ValidationError("Password must contain a symbol")
