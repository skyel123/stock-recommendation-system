"""Application-side authentication service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from uuid import uuid4

from finance_dashboard.models import User
from finance_dashboard.portfolio_repository import InMemoryUserRepository, UserRepository


class AuthService:
    def __init__(self, repository: UserRepository | None = None) -> None:
        self.repository = repository or InMemoryUserRepository()

    @staticmethod
    def _hash_password(password: str, salt: bytes | None = None) -> str:
        salt = salt or os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return base64.b64encode(salt + digest).decode()

    @classmethod
    def _verify_password(cls, password: str, encoded: str) -> bool:
        raw = base64.b64decode(encoded.encode())
        return hmac.compare_digest(cls._hash_password(password, raw[:16]), encoded)

    def signup(self, email: str, password: str) -> User:
        normalized = email.strip().lower()
        if "@" not in normalized or len(password) < 8:
            raise ValueError("Use a valid email and a password of at least 8 characters.")
        if self.repository.get_by_email(normalized):
            raise ValueError("An account with that email already exists.")
        return self.repository.create(User(str(uuid4()), normalized, self._hash_password(password)))

    def login(self, email: str, password: str) -> User:
        user = self.repository.get_by_email(email.strip().lower())
        if not user or not self._verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials.")
        return user