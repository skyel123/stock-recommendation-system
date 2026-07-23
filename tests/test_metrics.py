"""Tests for financial metric calculations."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from finance_dashboard.metrics import Metrics


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    rng = np.random.default_rng(42)
    aapl = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, len(dates)))
    msft = 200 * np.cumprod(1 + rng.normal(0.0008, 0.015, len(dates)))
    return pd.DataFrame({"AAPL": aapl, "MSFT": msft}, index=dates)


def test_rolling_volatility_returns_series(sample_prices: pd.DataFrame) -> None:
    result = Metrics.calculate_rolling_volatility(sample_prices["AAPL"], window=21)
    assert isinstance(result, pd.Series)
    assert result.notna().sum() > 0
    assert (result.dropna() >= 0).all()


def test_rolling_volatility_rejects_short_window(sample_prices: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="window"):
        Metrics.calculate_rolling_volatility(sample_prices["AAPL"], window=0)


def test_stock_comparison_normalizes_to_100(sample_prices: pd.DataFrame) -> None:
    result = Metrics.calculate_comparison(sample_prices, mode="normalized")
    assert list(result.columns) == ["AAPL", "MSFT"]
    for col in result.columns:
        first_valid = result[col].dropna().iloc[0]
        assert first_valid == pytest.approx(100.0)


def test_stock_comparison_raw_mode(sample_prices: pd.DataFrame) -> None:
    result = Metrics.calculate_comparison(sample_prices, mode="raw")
    pd.testing.assert_frame_equal(result, sample_prices)


def test_cumulative_returns_start_at_zero(sample_prices: pd.DataFrame) -> None:
    result = Metrics.calculate_cumulative_returns(sample_prices)
    for col in result.columns:
        assert result[col].iloc[0] == pytest.approx(0.0)


def test_sharpe_ratio_returns_series(sample_prices: pd.DataFrame) -> None:
    result = Metrics.calculate_sharpe_ratio(sample_prices["AAPL"], window=21)
    assert isinstance(result, pd.Series)
    assert result.notna().any()


def test_comparison_both_mode_returns_dict(sample_prices: pd.DataFrame) -> None:
    metrics = Metrics()
    result = metrics.calculate(
        "Stock Comparison",
        sample_prices,
        comparison_mode="both",
    )
    assert set(result.keys()) == {"normalized", "raw"}


def test_metric_registry_optional_metrics() -> None:
    from finance_dashboard.metric_registry import MetricRegistry

    registry = MetricRegistry()
    assert "Sharpe Ratio" in registry.optional_metrics()
    active = registry.active_metrics(["Sharpe Ratio"])
    assert any(m.name == "Sharpe Ratio" for m in active)


def test_correlation_matrix_is_square(sample_prices: pd.DataFrame) -> None:
    result = Metrics.calculate_correlation(sample_prices)
    assert result.shape == (2, 2)
    assert list(result.index) == list(result.columns)
    assert (result.loc["AAPL", "AAPL"] == pytest.approx(1.0))


def test_correlation_rejects_single_stock(sample_prices: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="at least two"):
        Metrics.calculate_correlation(sample_prices[["AAPL"]])


def test_filter_by_date_range(sample_prices: pd.DataFrame) -> None:
    start = pd.Timestamp("2024-01-15")
    end = pd.Timestamp("2024-02-15")
    filtered = Metrics.filter_by_date_range(sample_prices, start, end)
    assert filtered.index.min() >= start
    assert filtered.index.max() <= end


def test_load_from_csv_watchlist() -> None:
    from finance_dashboard.finance_data import FinanceData
    import io

    csv_data = """AAPL
MSFT
GOOGL"""
    fd = FinanceData()
    tickers = fd.load_from_csv(io.StringIO(csv_data))
    assert set(tickers) == {"AAPL", "MSFT", "GOOGL"}

    csv_data_2 = """AAPL, MSFT
GOOGL, TSLA"""
    tickers_2 = fd.load_from_csv(io.StringIO(csv_data_2))
    assert set(tickers_2) == {"AAPL", "MSFT", "GOOGL", "TSLA"}

def test_download_skips_tickers_that_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_dashboard.finance_data import FinanceData
    import finance_dashboard.finance_data as finance_data_module

    def fake_download(*args, **kwargs):
        if args and args[0] == ["AAPL"]:
            return pd.DataFrame(
                {"Close": [100.0, 101.0]},
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            )
        raise TimeoutError("timed out")

    monkeypatch.setattr(finance_data_module.yf, "download", fake_download)
    fd = FinanceData()
    prices = fd.download(["AAPL", "BAD"], date(2024, 1, 1), date(2024, 1, 3), timeout_seconds=3)

    assert list(prices.columns) == ["AAPL"]
    assert fd.tickers == ["AAPL"]


def test_download_raises_when_all_tickers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_dashboard.finance_data import FinanceData
    import finance_dashboard.finance_data as finance_data_module

    monkeypatch.setattr(
        finance_data_module.yf,
        "download",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("timed out")),
    )

    fd = FinanceData()
    with pytest.raises(ValueError, match="No usable price data"):
        fd.download(["BAD"], date(2024, 1, 1), date(2024, 1, 3), timeout_seconds=3)

def test_load_from_csv_empty_watchlist() -> None:
    from finance_dashboard.finance_data import FinanceData
    import io

    csv_data = """,,,
,,,
,,,"""
    fd = FinanceData()
    with pytest.raises(ValueError, match="CSV contains no valid ticker symbols"):
        fd.load_from_csv(io.StringIO(csv_data))

