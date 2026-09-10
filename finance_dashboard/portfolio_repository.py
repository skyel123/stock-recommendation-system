"""Persistence adapters for users and portfolios."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from finance_dashboard.models import Portfolio, User


class UserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def create(self, user: User) -> User: ...


class PortfolioRepository(ABC):
    @abstractmethod
    def create(self, portfolio: Portfolio) -> Portfolio: ...

    @abstractmethod
    def get(self, portfolio_id: str) -> Portfolio | None: ...

    @abstractmethod
    def list_for_user(self, user_id: str) -> list[Portfolio]: ...

    @abstractmethod
    def save(self, portfolio: Portfolio) -> Portfolio: ...

    @abstractmethod
    def delete(self, portfolio_id: str) -> None: ...


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email.lower()), None)

    def create(self, user: User) -> User:
        self.users[user.id] = user
        return user


class InMemoryPortfolioRepository(PortfolioRepository):
    def __init__(self) -> None:
        self.portfolios: dict[str, Portfolio] = {}

    def create(self, portfolio: Portfolio) -> Portfolio:
        self.portfolios[portfolio.id] = portfolio
        return portfolio

    def get(self, portfolio_id: str) -> Portfolio | None:
        return self.portfolios.get(portfolio_id)

    def list_for_user(self, user_id: str) -> list[Portfolio]:
        return [item for item in self.portfolios.values() if item.user_id == user_id]

    def save(self, portfolio: Portfolio) -> Portfolio:
        self.portfolios[portfolio.id] = portfolio
        return portfolio

    def delete(self, portfolio_id: str) -> None:
        self.portfolios.pop(portfolio_id, None)


class MongoRepositories(UserRepository, PortfolioRepository):
    """MongoDB Atlas adapter. Set MONGODB_URI and optionally MONGODB_DATABASE."""

    def __init__(self, uri: str | None = None, database: str | None = None) -> None:
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise RuntimeError("Install pymongo to use MongoDB persistence.") from exc
        uri = uri or os.getenv("MONGODB_URI")
        database = database or os.getenv("MONGODB_DATABASE")
        if not uri:
            try:
                import streamlit as st

                uri = st.secrets.get("MONGODB_URI")
                database = database or st.secrets.get("MONGODB_DATABASE")
            except (ImportError, FileNotFoundError):
                pass
        if not uri:
            raise ValueError("MONGODB_URI is required for MongoDB persistence.")
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[database or "finance_dashboard"]
        self.users = db["users"]
        self.portfolios = db["portfolios"]
        self.users.create_index("email", unique=True)
        self.portfolios.create_index([("user_id", 1), ("name", 1)], unique=True)

    def get_by_email(self, email: str) -> User | None:
        document = self.users.find_one({"email": email.lower()})
        return User.from_document(document) if document else None

    def create(self, user: User) -> User:
        self.users.insert_one(user.to_document())
        return user

    def create_portfolio(self, portfolio: Portfolio) -> Portfolio:
        self.portfolios.insert_one(portfolio.to_document())
        return portfolio

    def create(self, item: Any) -> Any:
        if isinstance(item, User):
            self.users.insert_one(item.to_document())
        else:
            self.portfolios.insert_one(item.to_document())
        return item

    def get(self, portfolio_id: str) -> Portfolio | None:
        document = self.portfolios.find_one({"_id": portfolio_id})
        return Portfolio.from_document(document) if document else None

    def list_for_user(self, user_id: str) -> list[Portfolio]:
        return [Portfolio.from_document(item) for item in self.portfolios.find({"user_id": user_id})]

    def save(self, portfolio: Portfolio) -> Portfolio:
        self.portfolios.replace_one({"_id": portfolio.id}, portfolio.to_document(), upsert=True)
        return portfolio

    def delete(self, portfolio_id: str) -> None:
        self.portfolios.delete_one({"_id": portfolio_id})