"""Application data models and MongoDB document conventions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    created_at: datetime = field(default_factory=utc_now)

    def to_document(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "User":
        return cls(document["_id"], document["email"], document["password_hash"], document["created_at"])


@dataclass
class Portfolio:
    id: str
    user_id: str
    name: str
    holdings: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(cls, user_id: str, name: str) -> "Portfolio":
        return cls(str(uuid4()), user_id, name.strip())

    def to_document(self) -> dict[str, Any]:
        document = self.__dict__.copy()
        document["_id"] = document.pop("id")
        return document

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "Portfolio":
        return cls(document["_id"], document["user_id"], document["name"], dict(document.get("holdings", {})), document["created_at"], document["updated_at"])
