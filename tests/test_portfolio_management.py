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


def test_portfolio_analysis_skips_small_clusters_and_labels_risk_groups() -> None:
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    prices = pd.DataFrame(
        {
            "A": 100 * (1.001 ** np.arange(len(dates))),
            "B": 100 * (1.002 ** np.arange(len(dates))),
            "C": 100 * (1.003 ** np.arange(len(dates))),
            "D": [100 + (i % 2) * 10 for i in range(len(dates))],
            "E": [100 + (i % 3) * 8 for i in range(len(dates))],
            "F": [100 + (i % 4) * 12 for i in range(len(dates))],
        },
        index=dates,
    )
    analysis = PortfolioAnalysis()

    small = analysis.analyze_portfolio(prices[["A", "B", "C"]])
    assert small["cluster_count"] is None
    assert set(small["metrics"].columns) == {"ticker", "period_return", "period_volatility"}
    assert small["metrics"].loc[small["metrics"]["ticker"] == "A", "period_return"].iloc[0] == pytest.approx(
        prices["A"].iloc[-1] / prices["A"].iloc[0] - 1
    )

    result = analysis.analyze_portfolio(prices)
    assert result["cluster_count"] == 3
    assert set(result["risk_groups"]["risk_group"]) <= {"Low Risk", "Medium Risk", "High Risk"}

    medium = analysis.analyze_portfolio(prices[["A", "B", "C", "D", "E"]])
    assert medium["cluster_count"] == 2
    assert set(medium["risk_groups"]["risk_group"]) <= {"Low Risk", "High Risk"}


def test_portfolio_analysis_handles_empty_portfolios() -> None:
    result = PortfolioAnalysis().analyze_portfolio(pd.DataFrame())

    assert result["metrics"].empty
    assert result["risk_groups"].empty
    assert result["cluster_count"] is None


def test_portfolio_analysis_uses_requested_volatility_window() -> None:
    dates = pd.date_range("2024-01-01", periods=40, freq="B")
    prices = pd.DataFrame(
        {"A": 100 + np.arange(len(dates)), "B": 100 + (np.arange(len(dates)) % 3) * 5},
        index=dates,
    )

    short_window = PortfolioAnalysis().analyze_portfolio(prices, window=5)
    long_window = PortfolioAnalysis().analyze_portfolio(prices, window=15)

    assert not short_window["metrics"].equals(long_window["metrics"])


def test_portfolio_analysis_rejects_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        PortfolioAnalysis().analyze_portfolio(pd.DataFrame(), window=1)
