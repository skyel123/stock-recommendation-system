"""Portfolio return, volatility, and unsupervised risk-group analysis."""

from __future__ import annotations

import pandas as pd

from finance_dashboard.metrics import TRADING_DAYS_PER_YEAR


class PortfolioAnalysis:
    @staticmethod
    def returns(prices: pd.DataFrame, frequency: str = "daily") -> pd.DataFrame:
        if frequency == "daily":
            return prices.pct_change().dropna(how="all")
        if frequency == "monthly":
            return prices.resample("ME").last().pct_change().dropna(how="all")
        raise ValueError("frequency must be daily or monthly")

    def volatility(self, prices: pd.DataFrame, frequency: str = "annualized") -> pd.DataFrame:
        if frequency == "annualized":
            return self.returns(prices, "daily").std().to_frame("volatility") * TRADING_DAYS_PER_YEAR**0.5
        if frequency == "daily":
            return self.returns(prices, "daily").std().to_frame("volatility")
        if frequency == "monthly":
            return self.returns(prices, "monthly").std().to_frame("volatility")
        raise ValueError("frequency must be daily, monthly, or annualized")

    def risk_groups(self, prices: pd.DataFrame, method: str = "kmeans", groups: int = 3) -> pd.DataFrame:
        from sklearn.cluster import DBSCAN, KMeans
        from sklearn.preprocessing import StandardScaler

        daily = self.returns(prices)
        features = pd.DataFrame({"return": daily.mean(), "volatility": daily.std() * TRADING_DAYS_PER_YEAR**0.5})
        scaled = StandardScaler().fit_transform(features.fillna(0))
        if method.lower() == "kmeans":
            labels = KMeans(n_clusters=min(groups, len(features)), n_init=10, random_state=42).fit_predict(scaled)
        elif method.lower() == "dbscan":
            labels = DBSCAN().fit_predict(scaled)
        else:
            raise ValueError("method must be kmeans or dbscan")
        return pd.DataFrame({"ticker": features.index, "risk_group": labels})

    @staticmethod
    def recommendations(prices: pd.DataFrame, ticker: str, limit: int = 3) -> pd.DataFrame:
        if ticker not in prices.columns or len(prices.columns) < 2:
            raise ValueError("Select a stock with comparable stocks available.")
        correlation = PortfolioAnalysis().returns(prices).corr()[ticker].drop(ticker)
        return correlation.abs().sort_values(ascending=False).head(limit).to_frame("similarity")
