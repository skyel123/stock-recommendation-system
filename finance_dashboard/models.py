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


@dataclass(eq=False)
class Holding:
    quantity: int
    purchase_price: float = 0.0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Holding):
            return (self.quantity, self.purchase_price) == (other.quantity, other.purchase_price)
        if isinstance(other, (int, float)):
            return self.quantity == other
        return NotImplemented

    def to_document(self) -> dict[str, Any]:
        return {"quantity": self.quantity, "purchase_price": self.purchase_price}


@dataclass
class Portfolio:
    id: str
    user_id: str
    name: str
    holdings: dict[str, Holding] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(cls, user_id: str, name: str) -> "Portfolio":
        return cls(str(uuid4()), user_id, name.strip())

    def to_document(self) -> dict[str, Any]:
        document = self.__dict__.copy()
        document["holdings"] = {
            ticker: holding.to_document() for ticker, holding in self.holdings.items()
        }
        document["_id"] = document.pop("id")
        return document

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "Portfolio":
        holdings = {
            ticker: value
            if isinstance(value, Holding)
            else Holding(
                quantity=int(value) if not isinstance(value, dict) else int(value.get("quantity", 0)),
                purchase_price=0.0
                if not isinstance(value, dict)
                else float(value.get("purchase_price", 0.0)),
            )
            for ticker, value in document.get("holdings", {}).items()
        }
        return cls(document["_id"], document["user_id"], document["name"], holdings, document["created_at"], document["updated_at"])
