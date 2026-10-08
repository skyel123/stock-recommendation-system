import numpy as np
import pandas as pd
import pytest

from finance_dashboard.stock_prediction import (
    FEATURE_COLUMNS,
    StockDirectionPredictor,
    StockFeatureEngineering,
)


def test_feature_engineering_sorts_prices_and_builds_direction_target() -> None:
    dates = pd.date_range("2024-01-01", periods=40, freq="B")
    prices = pd.DataFrame({"Close": np.arange(100.0, 140.0)}, index=dates).iloc[::-1]

    result = StockFeatureEngineering().prepare(prices)

    assert result.index.is_monotonic_increasing
    assert pd.isna(result.loc[dates[0], "Return_1D"])
    assert result.loc[dates[5], "Return_5D"] == pytest.approx(105 / 100 - 1)
    assert pd.isna(result.loc[dates[-1], "Target"])
    assert result.loc[dates[-2], "Target"] == 1
    assert result.loc[dates[-2], "Tomorrow_Close"] == result.loc[dates[-1], "Close"]
    assert set(FEATURE_COLUMNS).issubset(result.columns)


def test_feature_engineering_requires_close_column() -> None:
    with pytest.raises(ValueError, match="Close"):
        StockFeatureEngineering().prepare(pd.DataFrame({"AAPL": [100.0, 101.0]}))


def test_random_forest_returns_direction_and_feature_importance() -> None:
    dates = pd.date_range("2023-01-01", periods=160, freq="B")
    changes = np.where(np.arange(len(dates)) % 3 == 0, -0.5, 0.8)
    prices = pd.DataFrame({"Close": 100 + np.cumsum(changes)}, index=dates)

    result = StockDirectionPredictor().predict(prices)

    assert result["prediction"] in (0, 1)
    assert result["latest_close"] == pytest.approx(prices["Close"].iloc[-1])
    assert result["training_observations"] > 30
    assert set(result["feature_importance"]["feature"]) == set(FEATURE_COLUMNS)
    assert result["feature_importance"]["importance"].sum() == pytest.approx(1.0)