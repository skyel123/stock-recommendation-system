from datetime import date

import pandas as pd
import pytest
import numpy as np

from finance_dashboard.analysis import PortfolioAnalysis
from finance_dashboard.auth import AuthService
from finance_dashboard.portfolio_repository import InMemoryPortfolioRepository
from finance_dashboard.portfolio_service import PortfolioService


def test_portfolio_crud_and_holdings() -> None:
    service = PortfolioService(InMemoryPortfolioRepository())
    portfolio = service.create_portfolio("user-1", "Retirement")

    service.add_holding(portfolio.id, "aapl", 10, 100.50)
    service.add_holding(portfolio.id, "MSFT", 5, 200)
    service.edit_holding(portfolio.id, "AAPL", 12)
    service.remove_holding(portfolio.id, "MSFT")

    saved = service.get_portfolio(portfolio.id, "user-1")
    assert saved.name == "Retirement"
    assert saved.holdings["AAPL"].quantity == 12
    assert saved.holdings["AAPL"].purchase_price == 100.50
    assert service.list_portfolios("user-1")[0].id == portfolio.id


def test_holding_requires_a_whole_number_and_preserves_purchase_price() -> None:
    service = PortfolioService(InMemoryPortfolioRepository())
    portfolio = service.create_portfolio("user-1", "Long term")

    with pytest.raises(ValueError, match="whole-number"):
        service.add_holding(portfolio.id, "AAPL", 2.5, 100)

    service.add_holding(portfolio.id, "AAPL", 3, 125.75)
    saved = service.get_portfolio(portfolio.id, "user-1")
    assert saved.to_document()["holdings"]["AAPL"] == {
        "quantity": 3,
        "purchase_price": 125.75,
    }


def test_portfolio_access_is_scoped_to_user() -> None:
    service = PortfolioService(InMemoryPortfolioRepository())
    portfolio = service.create_portfolio("user-1", "Private")

    with pytest.raises(PermissionError):
        service.get_portfolio(portfolio.id, "user-2")


def test_auth_signup_login_and_duplicate_email() -> None:
    auth = AuthService()
    user = auth.signup("owner@example.com", "correct horse battery staple")

    assert user.email == "owner@example.com"
    assert auth.login("OWNER@example.com", "correct horse battery staple").id == user.id
    with pytest.raises(ValueError, match="already exists"):
        auth.signup("owner@example.com", "another password")
    with pytest.raises(ValueError, match="Invalid credentials"):
        auth.login("owner@example.com", "wrong")


def test_analysis_supports_daily_monthly_annualized_volatility() -> None:
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    prices = pd.DataFrame(
        {"AAPL": 100 * (1.001 ** np.arange(len(dates)))},
        index=dates,
    )
    analysis = PortfolioAnalysis()

    for frequency in ("daily", "monthly", "annualized"):
        result = analysis.volatility(prices, frequency=frequency)
        assert isinstance(result, pd.DataFrame)
        assert "AAPL" in result.index


def test_analysis_clusters_risk_groups() -> None:
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    prices = pd.DataFrame(
        {
            "LOW": [100 + i * 0.1 for i in range(len(dates))],
            "HIGH": [100 + (i % 2) * 10 for i in range(len(dates))],
        },
        index=dates,
    )
    result = PortfolioAnalysis().risk_groups(prices, method="kmeans", groups=2)
    assert set(result.columns) == {"ticker", "risk_group"}
    assert len(result) == 2
