"""Historical feature engineering and next-day stock direction prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


FEATURE_COLUMNS = ["Return_1D", "Return_5D", "Return_10D", "Volatility_20D"]


class StockFeatureEngineering:
    """Build lagged price features and next-trading-day direction labels."""

    @staticmethod
    def prepare(prices: pd.DataFrame) -> pd.DataFrame:
        if "Close" not in prices.columns:
            raise ValueError("Price data must contain a 'Close' column.")

        data = prices[["Close"]].copy().sort_index()
        data["Close"] = pd.to_numeric(data["Close"], errors="coerce")
        data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=["Close"])
        if data.empty:
            raise ValueError("Price data has no valid closing prices.")

        daily_return = data["Close"].pct_change(fill_method=None)
        data["Return_1D"] = daily_return
        data["Return_5D"] = data["Close"].pct_change(5, fill_method=None)
        data["Return_10D"] = data["Close"].pct_change(10, fill_method=None)
        data["Volatility_20D"] = daily_return.rolling(window=20).std()
        data["Tomorrow_Close"] = data["Close"].shift(-1)
        data["Target"] = (data["Tomorrow_Close"] > data["Close"]).astype("int64")
        data.loc[data["Tomorrow_Close"].isna(), "Target"] = np.nan
        return data


class StockDirectionPredictor:
    """Fit a random forest on historical features and predict the next direction."""

    def __init__(self) -> None:
        self.feature_engineering = StockFeatureEngineering()

    def predict(self, prices: pd.DataFrame) -> dict[str, int | float | pd.DataFrame]:
        data = self.feature_engineering.prepare(prices)
        valid_features = data[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
        training_mask = data["Target"].notna() & valid_features.notna().all(axis=1)
        training_data = data.loc[training_mask]
        latest_features = valid_features.dropna().tail(1)

        if len(training_data) < 30 or latest_features.empty:
            raise ValueError("Not enough historical data to generate a prediction.")

        model = RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(training_data[FEATURE_COLUMNS], training_data["Target"].astype(int))
        prediction = int(model.predict(latest_features)[0])
        importance = pd.DataFrame(
            {"feature": FEATURE_COLUMNS, "importance": model.feature_importances_}
        ).sort_values("importance", ascending=False, ignore_index=True)

        return {
            "prediction": prediction,
            "latest_close": float(data["Close"].iloc[-1]),
            "training_observations": len(training_data),
            "feature_importance": importance,
        }