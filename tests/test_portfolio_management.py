from datetime import date

import pandas as pd
import pytest
import numpy as np

from finance_dashboard.analysis import PortfolioAnalysis
from finance_dashboard.auth import AuthService
from finance_dashboard.portfolio_repository import (
    InMemoryPortfolioRepository,
    MongoRepositories,
    load_mongo_settings,
    persistence_warning_message,
)
from finance_dashboard.portfolio_assistant import PortfolioAssistant
from finance_dashboard.portfolio_repository import InMemoryConversationRepository
from finance_dashboard.models import Holding, Portfolio
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


def test_overview_aggregates_duplicate_holdings_and_values_current_shares() -> None:
    first = Portfolio.new("user-1", "First")
    second = Portfolio.new("user-1", "Second")
    first.holdings = {"AAPL": Holding(2, 100.0)}
    second.holdings = {"AAPL": Holding(3, 200.0), "MSFT": Holding(1, 50.0)}
    analysis = PortfolioAnalysis()
    combined = analysis.aggregate_holdings([first, second])
    assert combined["AAPL"].quantity == 5
    assert combined["AAPL"].purchase_price == pytest.approx(160.0)
    prices = pd.DataFrame(
        {"AAPL": [10.0, 12.0], "MSFT": [20.0, 25.0]},
        index=pd.date_range("2024-01-01", periods=2),
    )
    assert analysis.performance_series([first, second], prices).tolist() == [70.0, 85.0]


def test_risk_distribution_keeps_unclassifiable_investment_visible() -> None:
    portfolio = Portfolio.new("user-1", "Holdings")
    portfolio.holdings = {"A": Holding(2, 10), "B": Holding(1, 20)}
    distribution, unclassified = PortfolioAnalysis().risk_distribution(
        PortfolioAnalysis.aggregate_holdings([portfolio]), pd.DataFrame()
    )
    assert unclassified == 40
    assert distribution.to_dict("records") == [
        {"risk_group": "Unclassified", "investment_value": 40.0, "percentage": 0.0}
    ]


def test_risk_distribution_sanitizes_missing_purchase_prices_for_chart_hover() -> None:
    holdings = {"AAPL": Holding(2, float("nan")), "MSFT": Holding(1, 0.0)}
    distribution, unclassified = PortfolioAnalysis().risk_distribution(holdings, pd.DataFrame())
    assert distribution["percentage"].notna().all()
    assert distribution["investment_value"].notna().all()
    assert unclassified == 0.0


def test_portfolio_assistant_context_uses_existing_values_only() -> None:
    portfolio = Portfolio.new("user-1", "Retirement")
    portfolio.holdings = {"AAPL": Holding(2, 100.0)}
    prices = pd.DataFrame({"AAPL": [110.0, 125.0]}, index=pd.date_range("2024-01-01", periods=2))
    result = {
        "metrics": pd.DataFrame([{"ticker": "AAPL", "period_return": 0.25, "period_volatility": 0.1}]),
        "risk_groups": pd.DataFrame(),
        "cluster_count": None,
    }

    context = PortfolioAssistant.build_context(
        portfolio, prices, result, date(2024, 1, 1), date(2024, 1, 2), 21
    )

    assert context["holdings"]["AAPL"] == {
        "quantity": 2,
        "purchase_price": 100.0,
        "current_price": 125.0,
    }
    assert context["calculated_metrics"][0]["period_return"] == 0.25
    assert context["clustering"]["cluster_count"] is None


def test_conversation_repository_round_trips_messages() -> None:
    repository = InMemoryConversationRepository()
    messages = [{"role": "user", "content": "What is volatility?"}]

    repository.append_messages("user-1", "portfolio-1", messages)

    assert repository.list_messages("user-1", "portfolio-1") == messages
    assert repository.list_messages("user-2", "portfolio-1") == []


def test_mongo_settings_prefer_environment_over_streamlit_secrets(monkeypatch) -> None:
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "testdb")
    monkeypatch.setattr(
        "finance_dashboard.portfolio_repository._streamlit_secret",
        lambda name: "should-not-be-used",
    )

    uri, database = load_mongo_settings()

    assert uri == "mongodb://localhost:27017"
    assert database == "testdb"


def test_mongo_repositories_require_uri_without_contacting_atlas(monkeypatch) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.setattr("finance_dashboard.portfolio_repository._streamlit_secret", lambda name: None)

    with pytest.raises(ValueError, match="MONGODB_URI"):
        MongoRepositories()


def test_persistence_warning_includes_authentication_failure() -> None:
    warning = persistence_warning_message(
        RuntimeError("MongoDB authentication or connection failed. Update the Atlas database user password in MONGODB_URI.")
    )

    assert "authentication or connection failed" in warning
    assert ".streamlit/secrets.toml" in warning
    assert "in-memory storage" in warning
