"""Use-case operations for portfolio management."""

from __future__ import annotations

from finance_dashboard.models import Holding, Portfolio
from finance_dashboard.portfolio_repository import PortfolioRepository


class PortfolioService:
    def __init__(self, repository: PortfolioRepository) -> None:
        self.repository = repository

    def create_portfolio(self, user_id: str, name: str) -> Portfolio:
        if not name.strip():
            raise ValueError("Portfolio name is required.")
        return self.repository.create(Portfolio.new(user_id, name))

    def list_portfolios(self, user_id: str) -> list[Portfolio]:
        return self.repository.list_for_user(user_id)

    def get_portfolio(self, portfolio_id: str, user_id: str) -> Portfolio:
        portfolio = self.repository.get(portfolio_id)
        if not portfolio:
            raise KeyError("Portfolio not found.")
        if portfolio.user_id != user_id:
            raise PermissionError("Portfolio does not belong to this user.")
        return portfolio

    def add_holding(
        self,
        portfolio_id: str,
        ticker: str,
        quantity: int,
        purchase_price: float = 0.0,
    ) -> Portfolio:
        portfolio = self._owned(portfolio_id)
        normalized = ticker.strip().upper()
        if not normalized or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Ticker and a positive whole-number quantity are required.")
        if purchase_price < 0:
            raise ValueError("Purchase price cannot be negative.")
        portfolio.holdings[normalized] = Holding(quantity, float(purchase_price))
        return self.repository.save(portfolio)

    def edit_holding(
        self,
        portfolio_id: str,
        ticker: str,
        quantity: int,
        purchase_price: float | None = None,
    ) -> Portfolio:
        portfolio = self._owned(portfolio_id)
        existing = portfolio.holdings.get(ticker.strip().upper())
        return self.add_holding(
            portfolio_id,
            ticker,
            quantity,
            existing.purchase_price if purchase_price is None and existing else purchase_price or 0.0,
        )

    def remove_holding(self, portfolio_id: str, ticker: str) -> Portfolio:
        portfolio = self._owned(portfolio_id)
        portfolio.holdings.pop(ticker.strip().upper(), None)
        return self.repository.save(portfolio)

    def _owned(self, portfolio_id: str) -> Portfolio:
        portfolio = self.repository.get(portfolio_id)
        if not portfolio:
            raise KeyError("Portfolio not found.")
        return portfolio