"""Financial metric calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


class Metrics:
    """Compute volatility, comparison, and correlation metrics."""

    @staticmethod
    def filter_by_date_range(
        prices: pd.DataFrame,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> pd.DataFrame:
        if start > end:
            raise ValueError("Start date must be on or before end date.")
        return prices.loc[(prices.index >= start) & (prices.index <= end)].copy()

    @staticmethod
    def calculate_rolling_volatility(
        prices: pd.Series,
        window: int = 21,
    ) -> pd.Series:
        if window < 1:
            raise ValueError("window must be at least 1.")

        returns = prices.pct_change()
        rolling_std = returns.rolling(window=window).std()
        return rolling_std * np.sqrt(TRADING_DAYS_PER_YEAR)

    @staticmethod
    def calculate_comparison(prices: pd.DataFrame, mode: str = "normalized") -> pd.DataFrame:
        """Compare stocks using normalized index (100) or raw prices."""
        if mode == "raw":
            return prices.copy()

        normalized = prices.copy()
        for column in normalized.columns:
            first_value = normalized[column].dropna().iloc[0]
            normalized[column] = (normalized[column] / first_value) * 100
        return normalized

    @staticmethod
    def calculate_sharpe_ratio(prices: pd.Series, window: int = 21) -> pd.Series:
        if window < 2:
            raise ValueError("window must be at least 2.")

        returns = prices.pct_change()
        rolling_mean = returns.rolling(window=window).mean() * TRADING_DAYS_PER_YEAR
        rolling_std = returns.rolling(window=window).std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        return rolling_mean / rolling_std

    @staticmethod
    def calculate_cumulative_returns(prices: pd.DataFrame) -> pd.DataFrame:
        returns = prices.pct_change().fillna(0)
        return (1 + returns).cumprod() - 1

    @staticmethod
    def calculate_correlation(prices: pd.DataFrame) -> pd.DataFrame:
        if prices.shape[1] < 2:
            raise ValueError("Correlation requires at least two stocks.")

        returns = prices.pct_change().dropna()
        return returns.corr()

    @staticmethod
    def calculate_rolling_correlation(
        prices: pd.DataFrame,
        ticker_a: str,
        ticker_b: str,
        window: int = 21,
    ) -> pd.Series:
        if window < 2:
            raise ValueError("window must be at least 2.")

        returns = prices[[ticker_a, ticker_b]].pct_change()
        return returns[ticker_a].rolling(window).corr(returns[ticker_b])

    def calculate(
        self,
        metric_type: str,
        prices: pd.DataFrame,
        window: int = 21,
        ticker_a: str | None = None,
        ticker_b: str | None = None,
        comparison_mode: str = "normalized",
    ):
        """Dispatch metric calculation by type."""
        if metric_type == "Rolling Volatility":
            if not ticker_a or ticker_a not in prices.columns:
                raise ValueError("Select a valid stock for volatility.")
            return self.calculate_rolling_volatility(prices[ticker_a], window=window)

        if metric_type == "Stock Comparison":
            if comparison_mode == "both":
                return {
                    "normalized": self.calculate_comparison(prices, mode="normalized"),
                    "raw": self.calculate_comparison(prices, mode="raw"),
                }
            mode = "raw" if comparison_mode == "raw" else "normalized"
            return self.calculate_comparison(prices, mode=mode)

        if metric_type == "Correlation Matrix":
            return self.calculate_correlation(prices)

        if metric_type == "Rolling Correlation":
            if not ticker_a or not ticker_b:
                raise ValueError("Select two stocks for rolling correlation.")
            return self.calculate_rolling_correlation(
                prices, ticker_a, ticker_b, window=window
            )

        if metric_type == "Sharpe Ratio":
            if not ticker_a or ticker_a not in prices.columns:
                raise ValueError("Select a valid stock for Sharpe ratio.")
            return self.calculate_sharpe_ratio(prices[ticker_a], window=window)

        if metric_type == "Cumulative Returns":
            return self.calculate_cumulative_returns(prices)

        raise ValueError(f"Unknown metric type: {metric_type}")
